from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration
from tests.support.runtime_settings import override_runtime_settings


def test_workflow_pack_queue_policy_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/queue-policies")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["policy_count"] == 3
    advisor_policy = next(
        policy
        for policy in body["policies"]
        if policy["workflow_pack_id"] == "advisor_brief.pack"
        and policy["workflow_pack_version"] == "v1"
    )
    assert advisor_policy["policy_id"] == "queue-policy.advisor-brief.v1"
    assert advisor_policy["default_lane"] == "LATENCY_SENSITIVE"
    assert advisor_policy["allowed_lanes"] == ["LATENCY_SENSITIVE", "REVIEW_SUPPORT"]
    assert any(
        requirement["evidence_type"] == "queue_policy_evaluation"
        for requirement in advisor_policy["evidence_requirements"]
    )


def test_workflow_pack_queue_policy_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/queue-policies/advisor_brief.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["policy"]["policy_id"] == "queue-policy.advisor-brief.v1"
    assert body["policy"]["max_concurrent_runs_per_lane"] == 2
    assert any("version-scoped" in line for line in body["status_summary"])


def test_workflow_pack_queue_policy_detail_route_rejects_discovery_only_version(
    client: TestClient,
) -> None:
    response = client.get("/platform/workflow-packs/queue-policies/advisor_brief.pack/v2")

    assert response.status_code == 404
    assert "Unknown workflow-pack queue policy" in response.json()["detail"]


def test_workflow_pack_queue_status_reports_active_admission_without_worker_internals(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    lease = acquire_workflow_pack_queue_admission(registration=registration)

    try:
        response = client.get("/platform/workflow-packs/queue-status")
        detail_response = client.get(f"/platform/workflow-packs/queue-status/{lease.queue_item_id}")
    finally:
        release_workflow_pack_queue_admission(lease.queue_item_id)

    assert response.status_code == 200
    body = response.json()
    assert body["queue_source_mode"] == "memory"
    assert body["active_admission_count"] == 1
    assert len(body["active_items"]) == 1
    assert body["active_items"][0]["queue_item_id"] == lease.queue_item_id
    assert body["active_items"][0]["policy_id"] == "queue-policy.advisor-brief.v1"
    assert body["active_items"][0]["workflow_pack_id"] == "advisor_brief.pack"
    assert body["active_items"][0]["workflow_pack_version"] == "v1"
    assert body["active_items"][0]["lane"] == "LATENCY_SENSITIVE"
    assert body["active_items"][0]["state"] == "RUNNING"
    assert body["active_items"][0]["admitted_at"].endswith("Z")
    advisor_latency_lane = next(
        lane_status
        for lane_status in body["lane_statuses"]
        if lane_status["workflow_pack_id"] == "advisor_brief.pack"
        and lane_status["lane"] == "LATENCY_SENSITIVE"
    )
    assert advisor_latency_lane["active_count"] == 1
    assert advisor_latency_lane["max_concurrent_runs_per_lane"] == 2
    assert advisor_latency_lane["saturation_status"] == "HEALTHY"
    assert "worker_id" not in body["active_items"][0]

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["queue_item"]["queue_item_id"] == lease.queue_item_id
    assert detail_body["queue_item"]["state"] == "RUNNING"


def test_workflow_pack_queue_events_report_admission_history_without_worker_internals(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    lease = acquire_workflow_pack_queue_admission(
        registration=registration,
        caller_app="lotus-gateway",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-panel",
    )
    release_workflow_pack_queue_admission(lease.queue_item_id)

    catalog_response = client.get(
        "/platform/workflow-packs/queue-events",
        params={"workflow_pack_id": "advisor_brief.pack"},
    )
    detail_response = client.get(f"/platform/workflow-packs/queue-events/{lease.queue_item_id}")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["queue_event_source_mode"] == "memory"
    assert catalog_body["event_count"] == 5
    assert catalog_body["events"][0]["event_type"] == "ADMISSION_RELEASED"
    assert "worker_id" not in catalog_body["events"][0]

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["queue_item_id"] == lease.queue_item_id
    assert [event["event_type"] for event in detail_body["events"]] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
        "ADMISSION_ADMITTED",
        "ADMISSION_GRANTED",
        "ADMISSION_RELEASED",
    ]
    assert detail_body["events"][0]["caller_app"] == "lotus-gateway"
    assert detail_body["events"][0]["tenant_id"] == "tenant-sg-001"
    assert detail_body["events"][0]["workflow_surface"] == "advisor-brief-panel"
    assert detail_body["events"][2]["caller_app"] == "lotus-gateway"
    assert detail_body["events"][2]["tenant_id"] == "tenant-sg-001"


def test_workflow_pack_queue_event_detail_rejects_unknown_item(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/queue-events/wpq_missing")

    assert response.status_code == 404
    assert "Unknown workflow-pack queue item history" in response.json()["detail"]


def test_workflow_pack_queue_retry_decision_route_records_recovery_metadata(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    lease = acquire_workflow_pack_queue_admission(registration=registration)
    release_workflow_pack_queue_admission(
        lease.queue_item_id,
        now_utc=datetime.now(UTC) + timedelta(minutes=10),
    )
    decision_response = client.post(
        f"/platform/workflow-packs/queue-events/{lease.queue_item_id}/retry-decisions",
        json={
            "failure_code": "EXECUTION_TIMEOUT",
            "requested_by": "operator-a",
            "reason": "Retry after bounded queue timeout.",
            "evidence_ref": "support-ticket-queue-recovery-api",
        },
    )

    assert decision_response.status_code == 200
    decision_body = decision_response.json()
    assert decision_body["event"]["event_type"] == "RETRY_RECORDED"
    assert any("does not claim" in line for line in decision_body["status_summary"])

    detail_response = client.get(f"/platform/workflow-packs/queue-events/{lease.queue_item_id}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    retry_events = [
        event
        for event in detail_body["events"]
        if event["event_id"] == decision_body["event"]["event_id"]
    ]
    assert retry_events[0]["event_type"] == "RETRY_RECORDED"
    assert retry_events[0]["source_queue_item_id"] == lease.queue_item_id
    assert retry_events[0]["recovery_action_type"] == "RETRY"
    assert retry_events[0]["recovery_attempt_number"] == 1
    assert retry_events[0]["requested_by"] == "operator-a"
    assert retry_events[0]["evidence_ref"] == "support-ticket-queue-recovery-api"


def test_workflow_pack_queue_replay_decision_route_blocks_duplicate_replay(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    lease = acquire_workflow_pack_queue_admission(registration=registration)
    release_workflow_pack_queue_admission(lease.queue_item_id)

    first_response = client.post(
        f"/platform/workflow-packs/queue-events/{lease.queue_item_id}/replay-decisions",
        json={
            "requested_by": "operator-a",
            "reason": "Replay for controlled evidence comparison.",
            "evidence_ref": "support-ticket-queue-replay-api-1",
        },
    )
    second_response = client.post(
        f"/platform/workflow-packs/queue-events/{lease.queue_item_id}/replay-decisions",
        json={
            "requested_by": "operator-a",
            "reason": "Duplicate replay should be blocked.",
            "evidence_ref": "support-ticket-queue-replay-api-2",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["event"]["event_type"] == "REPLAY_RECORDED"
    assert second_response.status_code == 200
    blocked_event = second_response.json()["event"]
    assert blocked_event["event_type"] == "REPLAY_BLOCKED"
    assert blocked_event["recovery_action_type"] == "REPLAY"
    assert blocked_event["recovery_attempt_number"] == 2


def test_workflow_pack_queue_status_marks_lane_saturated_at_attention_threshold(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    leases = [
        acquire_workflow_pack_queue_admission(registration=registration),
        acquire_workflow_pack_queue_admission(registration=registration),
    ]

    try:
        response = client.get("/platform/workflow-packs/queue-status")
    finally:
        for lease in leases:
            release_workflow_pack_queue_admission(lease.queue_item_id)

    assert response.status_code == 200
    body = response.json()
    advisor_latency_lane = next(
        lane_status
        for lane_status in body["lane_statuses"]
        if lane_status["workflow_pack_id"] == "advisor_brief.pack"
        and lane_status["lane"] == "LATENCY_SENSITIVE"
    )
    assert advisor_latency_lane["active_count"] == 2
    assert advisor_latency_lane["saturation_status"] == "SATURATED"


def test_workflow_pack_queue_status_detail_rejects_unknown_item(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/queue-status/wpq_missing")

    assert response.status_code == 404
    assert "Unknown active workflow-pack queue item" in response.json()["detail"]


def test_workflow_pack_queue_policy_routes_degrade_when_sql_registry_store_is_unmigrated(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-queue-policy-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_registry_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            catalog_response = durable_client.get("/platform/workflow-packs/queue-policies")
            detail_response = durable_client.get(
                "/platform/workflow-packs/queue-policies/advisor_brief.pack/v1"
            )
            status_response = durable_client.get("/platform/workflow-packs/queue-status")
            status_detail_response = durable_client.get(
                "/platform/workflow-packs/queue-status/wpq_missing"
            )

    for response in (
        catalog_response,
        detail_response,
        status_response,
        status_detail_response,
    ):
        assert response.status_code == 503
        assert "Workflow-pack registry store is not ready." in response.json()["detail"]
        assert "MIGRATION_REQUIRED" in response.json()["detail"]


def test_workflow_pack_queue_event_routes_degrade_when_sql_event_store_is_unmigrated(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-queue-events-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_queue_event_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            catalog_response = durable_client.get("/platform/workflow-packs/queue-events")
            detail_response = durable_client.get(
                "/platform/workflow-packs/queue-events/wpq_missing"
            )

    for response in (catalog_response, detail_response):
        assert response.status_code == 503
        assert "Workflow-pack queue event store is not ready:" in response.json()["detail"]
        assert "MIGRATION_REQUIRED" in response.json()["detail"]
