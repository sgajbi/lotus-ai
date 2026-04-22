import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.contracts.workflow_packs import (
    WorkflowPackCallerIdentityClass,
    WorkflowPackEnvironment,
)
from app.services.artifact_store import get_artifact_object_store
from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration
from tests.support.workflow_pack_fixtures import (
    advisor_brief_task_execution_request,
    advisor_brief_workflow_pack_execution_request_json,
)
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


def test_workflow_pack_execution_records_queue_request_snapshot_artifact(
    client: TestClient,
) -> None:
    correlation_id = "corr-queue-request-snapshot-api"
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(correlation_id=correlation_id),
    )

    assert execute_response.status_code == 200

    catalog_response = client.get(
        "/platform/workflow-packs/queue-events",
        params={"workflow_pack_id": "advisor_brief.pack"},
    )

    assert catalog_response.status_code == 200
    body = catalog_response.json()
    matching_events = [
        event for event in body["events"] if event["correlation_id"] == correlation_id
    ]
    assert [event["event_type"] for event in reversed(matching_events)] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
        "ADMISSION_ADMITTED",
        "ADMISSION_GRANTED",
        "ADMISSION_RELEASED",
    ]
    assert all(len(event["artifact_refs"]) == 1 for event in matching_events)
    snapshot_ref = matching_events[0]["artifact_refs"][0]
    assert all(event["artifact_refs"] == [snapshot_ref] for event in matching_events)
    assert snapshot_ref["domain"] == "workflow_pack"
    assert snapshot_ref["artifact_type"] == "queue_request_snapshot"
    assert snapshot_ref["source_object_kind"] == "workflow_pack_queue_item"
    assert snapshot_ref["source_object_id"] == matching_events[0]["queue_item_id"]
    assert snapshot_ref["retention_posture"] == "retained_for_recovery"
    assert "task_request" not in matching_events[0]
    assert "payload" not in matching_events[0]
    snapshot_object_key = snapshot_ref["storage_reference"].partition("://")[2]
    snapshot_object = get_artifact_object_store().get_object(object_key=snapshot_object_key)
    assert snapshot_object is not None
    snapshot_payload = json.loads(snapshot_object.payload)
    assert snapshot_payload["queue_item_id"] == matching_events[0]["queue_item_id"]
    assert snapshot_payload["registration_ref"] == "advisor_brief.pack@v1"
    assert snapshot_payload["workflow_authority_owner"] == "lotus-gateway"
    assert snapshot_payload["queue_lane"] == "LATENCY_SENSITIVE"
    assert snapshot_payload["environment"] == "DEVELOPMENT"
    assert snapshot_payload["caller_identity_class"] == "BANKER_PRODUCT"
    assert snapshot_payload["task_request"]["caller"]["correlation_id"] == correlation_id

    replay_response = client.post(
        f"/platform/workflow-packs/queue-events/{matching_events[0]['queue_item_id']}/replay-decisions",
        json={
            "requested_by": "operator-a",
            "reason": "Replay after comparing queue request snapshot evidence.",
            "evidence_ref": "support-ticket-queue-snapshot-replay",
        },
    )

    assert replay_response.status_code == 200
    replay_event = replay_response.json()["event"]
    assert replay_event["event_type"] == "REPLAY_RECORDED"
    assert replay_event["artifact_refs"] == [snapshot_ref]


def test_workflow_pack_queue_retry_execution_replays_retained_request_snapshot(
    client: TestClient,
) -> None:
    correlation_id = "corr-queue-retry-execution-api"
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    lease = acquire_workflow_pack_queue_admission(
        registration=registration,
        task_request=advisor_brief_task_execution_request(correlation_id=correlation_id),
        environment=WorkflowPackEnvironment.DEVELOPMENT,
        caller_identity_class=WorkflowPackCallerIdentityClass.BANKER_PRODUCT,
    )
    release_workflow_pack_queue_admission(
        lease.queue_item_id,
        now_utc=datetime.now(UTC) + timedelta(minutes=10),
    )

    response = client.post(
        f"/platform/workflow-packs/queue-events/{lease.queue_item_id}/retry-executions",
        json={
            "failure_code": "EXECUTION_TIMEOUT",
            "requested_by": "operator-a",
            "reason": "Retry after bounded queue timeout.",
            "evidence_ref": "support-ticket-queue-retry-execution-api",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision_event"]["event_type"] == "RETRY_RECORDED"
    assert body["decision_event"]["artifact_refs"]
    assert body["execution"]["workflow_pack_run"]["registration_ref"] == "advisor_brief.pack@v1"
    assert (
        body["execution"]["execution"]["audit"]["workflow_pack_run_id"]
        == (body["execution"]["workflow_pack_run"]["run_id"])
    )
    assert any(
        "executed from the retained request snapshot" in line for line in body["status_summary"]
    )


def test_workflow_pack_queue_retry_execution_requires_executable_snapshot(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    lease = acquire_workflow_pack_queue_admission(registration=registration)
    release_workflow_pack_queue_admission(
        lease.queue_item_id,
        now_utc=datetime.now(UTC) + timedelta(minutes=10),
    )

    response = client.post(
        f"/platform/workflow-packs/queue-events/{lease.queue_item_id}/retry-executions",
        json={
            "failure_code": "EXECUTION_TIMEOUT",
            "requested_by": "operator-a",
            "reason": "Retry should require a retained request snapshot.",
            "evidence_ref": "support-ticket-queue-retry-execution-missing-snapshot",
        },
    )

    assert response.status_code == 409
    assert "requires a request snapshot artifact ref" in response.json()["detail"]
    detail_response = client.get(f"/platform/workflow-packs/queue-events/{lease.queue_item_id}")
    assert all(
        event["event_type"] != "RETRY_RECORDED" for event in detail_response.json()["events"]
    )


def test_workflow_pack_queue_replay_execution_uses_normal_execution_path(
    client: TestClient,
) -> None:
    correlation_id = "corr-queue-replay-execution-api"
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(correlation_id=correlation_id),
    )
    assert execute_response.status_code == 200
    catalog_response = client.get(
        "/platform/workflow-packs/queue-events",
        params={"workflow_pack_id": "advisor_brief.pack"},
    )
    source_queue_item_id = next(
        event["queue_item_id"]
        for event in catalog_response.json()["events"]
        if event["correlation_id"] == correlation_id and event["event_type"] == "ADMISSION_RELEASED"
    )

    response = client.post(
        f"/platform/workflow-packs/queue-events/{source_queue_item_id}/replay-executions",
        json={
            "requested_by": "operator-a",
            "reason": "Replay from governed queue snapshot.",
            "evidence_ref": "support-ticket-queue-replay-execution-api",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision_event"]["event_type"] == "REPLAY_RECORDED"
    assert body["execution"]["workflow_pack_run"]["registration_ref"] == "advisor_brief.pack@v1"
    assert (
        body["execution"]["workflow_pack_run"]["run_id"]
        != (execute_response.json()["workflow_pack_run"]["run_id"])
    )


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
