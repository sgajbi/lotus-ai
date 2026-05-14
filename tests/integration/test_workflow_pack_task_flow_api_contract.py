from pathlib import Path

from fastapi.testclient import TestClient

from app.contracts.workflow_pack_runs import WorkflowPackRunReviewState, WorkflowPackRunRuntimeState
from app.contracts.workflow_pack_task_flows import WorkflowPackTaskFlowStatus
from app.main import app
from app.services.workflow_pack_task_flow_service import (
    create_task_flow,
    record_task_flow_checkpoint,
)
from app.services.workflow_pack_task_flow_store import reset_workflow_pack_task_flow_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.workflow_pack_task_flow_fixtures import (
    workflow_pack_task_flow_checkpoint,
    workflow_pack_task_flow_descriptor,
)


def test_workflow_pack_task_flow_catalog_starts_empty(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/task-flows")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["task_flow_store_mode"] == "memory"
    assert body["task_flow_count"] == 0
    assert body["active_count"] == 0
    assert body["waiting_for_review_count"] == 0
    assert body["blocked_count"] == 0
    assert body["terminal_count"] == 0
    assert body["filters_applied"] == {"limit": 100}
    assert body["task_flows"] == []


def test_workflow_pack_task_flow_catalog_limits_newest_flows_first(client: TestClient) -> None:
    for index in range(3):
        timestamp = f"2026-04-21T01:0{index}:00Z"
        create_task_flow(
            workflow_pack_task_flow_descriptor(
                task_flow_id=f"task-flow-00{index}",
                updated_at=timestamp,
            ).model_copy(
                update={
                    "created_at": timestamp,
                    "run_refs": [f"run-00{index}"],
                    "runtime_states": {f"run-00{index}": WorkflowPackRunRuntimeState.STAGED},
                    "review_states": {
                        f"run-00{index}": WorkflowPackRunReviewState.AWAITING_REVIEW
                    },
                }
            )
        )

    response = client.get("/platform/workflow-packs/task-flows", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert [flow["task_flow_id"] for flow in body["task_flows"]] == [
        "task-flow-002",
        "task-flow-001",
    ]
    assert "task-flow-000" not in {flow["task_flow_id"] for flow in body["task_flows"]}


def test_workflow_pack_task_flow_catalog_detail_and_checkpoints(
    client: TestClient,
) -> None:
    create_task_flow(
        workflow_pack_task_flow_descriptor(
            flow_status=WorkflowPackTaskFlowStatus.RUNNING,
            current_step_id="draft-brief",
        )
    )
    record_task_flow_checkpoint(
        task_flow_id="task-flow-001",
        checkpoint=workflow_pack_task_flow_checkpoint(),
        resulting_status=WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        current_step_id="draft-brief",
        updated_at="2026-04-21T01:01:00Z",
    )

    catalog_response = client.get(
        "/platform/workflow-packs/task-flows",
        params={
            "workflow_pack_id": "advisor_brief.pack",
            "caller": "lotus-gateway",
            "tenant_id": "tenant-sg-001",
            "workflow_surface": "advisor-brief-panel",
            "flow_status": "WAITING_FOR_REVIEW",
            "supportability_status": "ACTION_REQUIRED",
        },
    )

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["task_flow_count"] == 1
    assert catalog_body["active_count"] == 1
    assert catalog_body["waiting_for_review_count"] == 1
    assert catalog_body["terminal_count"] == 0
    assert catalog_body["filters_applied"] == {
        "limit": 100,
        "workflow_pack_id": "advisor_brief.pack",
        "caller": "lotus-gateway",
        "tenant_id": "tenant-sg-001",
        "workflow_surface": "advisor-brief-panel",
        "flow_status": "WAITING_FOR_REVIEW",
        "supportability_status": "ACTION_REQUIRED",
    }
    task_flow = catalog_body["task_flows"][0]
    assert task_flow["task_flow_id"] == "task-flow-001"
    assert task_flow["flow_status"] == "WAITING_FOR_REVIEW"
    assert task_flow["runtime_states"] == {"run-001": "STAGED"}
    assert task_flow["review_states"] == {"run-001": "AWAITING_REVIEW"}
    assert task_flow["checkpoint_refs"] == ["checkpoint-001"]

    detail_response = client.get("/platform/workflow-packs/task-flows/task-flow-001")
    checkpoints_response = client.get(
        "/platform/workflow-packs/task-flows/task-flow-001/checkpoints"
    )

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["task_flow"]["task_flow_id"] == "task-flow-001"
    assert detail_body["checkpoints"][0]["checkpoint_id"] == "checkpoint-001"
    assert detail_body["checkpoints"][0]["evidence_refs"][0]["evidence_type"] == (
        "unit_test_evidence"
    )

    assert checkpoints_response.status_code == 200
    checkpoints_body = checkpoints_response.json()
    assert checkpoints_body["task_flow_id"] == "task-flow-001"
    assert checkpoints_body["checkpoint_count"] == 1
    assert checkpoints_body["checkpoints"][0]["transition"] == "STEP_STARTED"


def test_workflow_pack_task_flow_routes_return_404_for_unknown_task_flow(
    client: TestClient,
) -> None:
    detail_response = client.get("/platform/workflow-packs/task-flows/missing-flow")
    checkpoints_response = client.get(
        "/platform/workflow-packs/task-flows/missing-flow/checkpoints"
    )

    assert detail_response.status_code == 404
    assert "Unknown workflow-pack task flow" in detail_response.json()["detail"]
    assert checkpoints_response.status_code == 404
    assert "Unknown workflow-pack task flow" in checkpoints_response.json()["detail"]


def test_workflow_pack_task_flow_routes_degrade_for_unmigrated_sql_store(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-api-unmigrated.db'}"

    with override_runtime_settings(
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as client:
            response = client.get("/platform/workflow-packs/task-flows")

    assert response.status_code == 503
    assert "MIGRATION_REQUIRED" in response.json()["detail"]


def test_workflow_pack_task_flow_routes_read_sql_backed_state_after_restart(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-api.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        create_task_flow(
            workflow_pack_task_flow_descriptor(
                flow_status=WorkflowPackTaskFlowStatus.RUNNING,
                current_step_id="draft-brief",
            )
        )
        record_task_flow_checkpoint(
            task_flow_id="task-flow-001",
            checkpoint=workflow_pack_task_flow_checkpoint(),
            resulting_status=WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
            current_step_id="draft-brief",
            updated_at="2026-04-21T01:01:00Z",
        )
        reset_workflow_pack_task_flow_store_cache()

        with TestClient(app) as client:
            response = client.get("/platform/workflow-packs/task-flows/task-flow-001")

    assert response.status_code == 200
    body = response.json()
    assert body["task_flow_store_mode"] == "sqlalchemy"
    assert body["task_flow"]["flow_status"] == "WAITING_FOR_REVIEW"
    assert body["checkpoints"][0]["checkpoint_id"] == "checkpoint-001"
