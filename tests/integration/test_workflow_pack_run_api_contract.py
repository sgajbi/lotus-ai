from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.workflow_pack_fixtures import (
    advisor_brief_task_execution_request_json,
    advisor_brief_workflow_pack_execution_request_json,
)


def test_workflow_pack_run_catalog_starts_empty(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run_store_mode"] == "memory"
    assert body["run_count"] == 0
    assert body["runs"] == []


def test_workflow_pack_run_catalog_and_detail_record_advisor_brief_execution(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(correlation_id="corr-pack-run-api-001"),
    )
    assert execute_response.status_code == 200

    catalog_response = client.get("/platform/workflow-packs/runs")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["run_count"] == 1
    assert catalog_body["awaiting_review_count"] == 1
    assert catalog_body["completed_count"] == 1
    run = catalog_body["runs"][0]
    assert run["pack_id"] == "advisor_brief.pack"
    assert run["registration_ref"] == "advisor_brief.pack@v1"
    assert run["runtime_state"] == "COMPLETED"
    assert run["review_state"] == "AWAITING_REVIEW"
    assert run["allowed_review_actions"] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert len(run["artifact_refs"]) == 1
    assert run["artifact_refs"][0]["domain"] == "workflow_pack"
    assert run["artifact_refs"][0]["artifact_type"] == "run_output_summary"

    detail_response = client.get(f"/platform/workflow-packs/runs/{run['run_id']}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["run_id"] == run["run_id"]
    assert detail_body["run"]["artifact_refs"][0]["source_object_id"] == run["run_id"]
    assert detail_body["events"][0]["event_type"] == "RUN_RECORDED"
    assert detail_body["run"]["workflow_surface"] == "advisor-brief-workspace"


def test_workflow_pack_execute_route_records_explicit_run_and_returns_run_id(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert (
        body["execution"]["audit"]["workflow_pack_run_id"]
        == body["workflow_pack_run"]["run_id"]
    )
    assert body["workflow_pack_run"]["workflow_surface"] == "advisor-brief-workspace"


def test_workflow_pack_execute_route_defaults_workflow_surface_from_binding(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-default-surface-001",
            workflow_surface=None,
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["workflow_pack_run"]["workflow_surface"] == "advisor-brief-workspace"


def test_workflow_pack_execute_route_rejects_wrong_task_for_binding(client: TestClient) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-wrong-task-001",
            task_id="summarize.v1",
        ),
    )

    assert execute_response.status_code == 409


def test_workflow_pack_execute_route_rejects_denied_surface(client: TestClient) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-denied-001",
            workflow_surface="unsupported-surface",
        ),
    )

    assert execute_response.status_code == 403


def test_workflow_pack_run_detail_rejects_unknown_run(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/unknown-run")

    assert response.status_code == 404


def test_workflow_pack_run_review_action_updates_review_state(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-review-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.100",
            "reason": "Advisor brief accepted for bounded downstream workflow use.",
        },
    )

    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["run"]["review_state"] == "ACCEPTED"
    assert review_body["run"]["allowed_review_actions"] == ["SUPERSEDE"]
    assert review_body["events"][0]["event_type"] == "REVIEW_STATE_UPDATED"
    detail_response = client.get(f"/platform/workflow-packs/runs/{run_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["run"]["review_state"] == "ACCEPTED"


def test_workflow_pack_run_consumer_view_groups_runtime_review_and_lineage(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-consumer-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    consumer_view_response = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view")

    assert consumer_view_response.status_code == 200
    body = consumer_view_response.json()
    assert body["runtime"]["state"] == "COMPLETED"
    assert body["review"]["state"] == "AWAITING_REVIEW"
    assert body["review"]["allowed_actions"] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert body["lineage"]["workflow_authority_owner"] == "lotus-gateway"
    assert "advisor_brief_status" in body["provenance"]["structured_output_keys"]
    assert len(body["provenance"]["artifact_refs"]) == 1
    assert body["provenance"]["artifact_refs"][0]["domain"] == "workflow_pack"


def test_workflow_pack_run_operator_profile_reports_supportability_posture(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-operator-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    profile_response = client.get(f"/platform/workflow-packs/runs/{run_id}/operator-profile")

    assert profile_response.status_code == 200
    body = profile_response.json()
    assert body["run_id"] == run_id
    assert body["supportability_status"] == "ACTION_REQUIRED"
    assert body["review_pending"] is True
    assert body["artifact_ref_count"] == 1
    assert any(finding["finding_id"] == "review_pending" for finding in body["findings"])


def test_workflow_pack_run_operator_profile_rejects_unknown_run(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/unknown-run/operator-profile")

    assert response.status_code == 404


def test_workflow_pack_run_catalog_supports_sqlalchemy_store_mode(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-api.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as client:
            execute_response = client.post(
                "/ai/tasks/execute",
                json=advisor_brief_task_execution_request_json(
                    correlation_id="corr-pack-run-api-sql-001"
                ),
            )
            assert execute_response.status_code == 200

            catalog_response = client.get("/platform/workflow-packs/runs")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["run_store_mode"] == "sqlalchemy"
    assert catalog_body["run_count"] == 1
    assert len(catalog_body["runs"][0]["artifact_refs"]) == 1
    assert catalog_body["runs"][0]["artifact_refs"][0]["domain"] == "workflow_pack"
