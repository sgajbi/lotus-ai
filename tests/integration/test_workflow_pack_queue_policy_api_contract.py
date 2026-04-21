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
    assert body["active_items"] == [
        {
            "queue_item_id": lease.queue_item_id,
            "policy_id": "queue-policy.advisor-brief.v1",
            "workflow_pack_id": "advisor_brief.pack",
            "workflow_pack_version": "v1",
            "lane": "LATENCY_SENSITIVE",
            "state": "RUNNING",
        }
    ]
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
