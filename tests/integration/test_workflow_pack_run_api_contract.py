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
    assert body["filters_applied"] == {"limit": 100}
    assert body["ready_count"] == 0
    assert body["action_required_count"] == 0
    assert body["historical_count"] == 0
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
    assert catalog_body["filters_applied"] == {"limit": 100}
    assert catalog_body["awaiting_review_count"] == 1
    assert catalog_body["completed_count"] == 1
    assert catalog_body["ready_count"] == 0
    assert catalog_body["action_required_count"] == 1
    assert catalog_body["historical_count"] == 0
    run = catalog_body["runs"][0]
    assert run["pack_id"] == "advisor_brief.pack"
    assert run["registration_ref"] == "advisor_brief.pack@v1"
    assert run["runtime_state"] == "COMPLETED"
    assert run["review_state"] == "AWAITING_REVIEW"
    assert run["supportability_status"] == "ACTION_REQUIRED"
    assert run["allowed_review_actions"] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert run["review_summary"]["latest_review_event_at"] is None
    assert run["review_summary"]["latest_review_actor"] is None
    assert run["review_summary"]["review_transition_count"] == 0
    assert run["review_summary"]["has_review_history"] is False
    assert len(run["artifact_refs"]) == 1
    assert run["artifact_refs"][0]["domain"] == "workflow_pack"
    assert run["artifact_refs"][0]["artifact_type"] == "run_output_summary"

    detail_response = client.get(f"/platform/workflow-packs/runs/{run['run_id']}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["run_id"] == run["run_id"]
    assert detail_body["review"]["state"] == "AWAITING_REVIEW"
    assert detail_body["review"]["latest_review_event_at"] is None
    assert detail_body["review"]["latest_review_actor"] is None
    assert detail_body["review"]["review_transition_count"] == 0
    assert detail_body["review"]["has_review_history"] is False
    assert detail_body["provenance"]["artifact_ref_count"] == 1
    assert detail_body["provenance"]["artifact_types"] == ["run_output_summary"]
    assert detail_body["provenance"]["evidence_descriptor_count"] >= 1
    assert "task_contract" in detail_body["provenance"]["evidence_types"]
    assert detail_body["supportability"]["status"] == "ACTION_REQUIRED"
    assert detail_body["supportability"]["review_pending"] is True
    assert detail_body["run"]["artifact_refs"][0]["source_object_id"] == run["run_id"]
    assert detail_body["events"][0]["event_type"] == "RUN_RECORDED"
    assert detail_body["run"]["workflow_surface"] == "advisor-brief-workspace"


def test_workflow_pack_run_catalog_route_supports_bounded_filters(
    client: TestClient,
) -> None:
    first_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-filter-001",
            caller_app="lotus-gateway",
            tenant_id="tenant-sg-001",
        ),
    )
    assert first_execute_response.status_code == 200
    second_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-filter-002",
            caller_app="lotus-gateway",
            tenant_id="tenant-us-002",
        ),
    )
    assert second_execute_response.status_code == 200

    all_runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    accepted_run_id = all_runs[0]["run_id"]
    awaiting_run_id = all_runs[1]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{accepted_run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.101",
            "reason": "Accepted for catalog filter coverage.",
        },
    )
    assert review_response.status_code == 200

    filtered_response = client.get(
        "/platform/workflow-packs/runs",
        params={
            "registration_ref": "advisor_brief.pack@v1",
            "caller_app": "lotus-gateway",
            "tenant_id": "tenant-sg-001",
            "workflow_surface": "advisor-brief-workspace",
            "runtime_state": "COMPLETED",
            "review_state": "AWAITING_REVIEW",
            "supportability_status": "ACTION_REQUIRED",
            "workflow_authority_owner": "lotus-gateway",
            "limit": 1,
        },
    )

    assert filtered_response.status_code == 200
    body = filtered_response.json()
    assert body["filters_applied"] == {
        "limit": 1,
        "registration_ref": "advisor_brief.pack@v1",
        "caller_app": "lotus-gateway",
        "tenant_id": "tenant-sg-001",
        "workflow_surface": "advisor-brief-workspace",
        "runtime_state": "COMPLETED",
        "review_state": "AWAITING_REVIEW",
        "supportability_status": "ACTION_REQUIRED",
        "workflow_authority_owner": "lotus-gateway",
    }
    assert body["run_count"] == 1
    assert body["ready_count"] == 0
    assert body["action_required_count"] == 1
    assert body["historical_count"] == 0
    assert [run["run_id"] for run in body["runs"]] == [awaiting_run_id]
    assert body["runs"][0]["caller_app"] == "lotus-gateway"
    assert body["runs"][0]["tenant_id"] == "tenant-sg-001"
    assert body["runs"][0]["workflow_surface"] == "advisor-brief-workspace"
    assert body["runs"][0]["supportability_status"] == "ACTION_REQUIRED"


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
    catalog_response = client.get("/platform/workflow-packs/runs")
    assert catalog_response.status_code == 200
    catalog_run = catalog_response.json()["runs"][0]
    assert catalog_run["review_summary"]["latest_review_event_at"] is not None
    assert catalog_run["review_summary"]["latest_review_actor"] == "review:banker.sg.100"
    assert catalog_run["review_summary"]["review_transition_count"] == 1
    assert catalog_run["review_summary"]["has_review_history"] is True
    detail_response = client.get(f"/platform/workflow-packs/runs/{run_id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["review_state"] == "ACCEPTED"
    assert detail_body["review"]["state"] == "ACCEPTED"
    assert detail_body["provenance"]["artifact_ref_count"] == 1
    assert "task_contract" in detail_body["provenance"]["evidence_types"]
    assert detail_body["review"]["latest_review_event_at"] is not None
    assert detail_body["review"]["latest_review_actor"] == "review:banker.sg.100"
    assert detail_body["review"]["review_transition_count"] == 1
    assert detail_body["review"]["has_review_history"] is True


def test_workflow_pack_run_review_action_allows_operator_caller(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-review-operator-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-platform",
            "reviewed_by": "ops.sg.platform.001",
            "reason": "Platform operator recorded bounded review acceptance.",
        },
    )

    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["run"]["review_state"] == "ACCEPTED"
    assert review_body["run"]["allowed_review_actions"] == ["SUPERSEDE"]
    assert review_body["events"][0]["event_type"] == "REVIEW_STATE_UPDATED"
    assert review_body["events"][0]["actor"] == "review:ops.sg.platform.001"

    catalog_response = client.get("/platform/workflow-packs/runs")
    assert catalog_response.status_code == 200
    catalog_run = catalog_response.json()["runs"][0]
    assert catalog_run["review_summary"]["latest_review_actor"] == "review:ops.sg.platform.001"
    assert catalog_run["review_summary"]["review_transition_count"] == 1


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
    assert body["review"]["latest_review_event_at"] is None
    assert body["review"]["latest_review_actor"] is None
    assert body["review"]["review_transition_count"] == 0
    assert body["review"]["has_review_history"] is False
    assert body["provenance_summary"]["artifact_ref_count"] == 1
    assert body["provenance_summary"]["artifact_types"] == ["run_output_summary"]
    assert body["provenance_summary"]["evidence_descriptor_count"] >= 1
    assert "task_contract" in body["provenance_summary"]["evidence_types"]
    assert body["supportability"]["status"] == "ACTION_REQUIRED"
    assert body["supportability"]["review_pending"] is True
    assert body["supportability"]["superseded"] is False
    assert body["supportability"]["partial_output_visible"] is False
    assert body["lineage"]["workflow_authority_owner"] == "lotus-gateway"
    assert "advisor_brief_status" in body["provenance"]["structured_output_keys"]
    assert len(body["provenance"]["artifact_refs"]) == 1
    assert body["provenance"]["artifact_refs"][0]["domain"] == "workflow_pack"


def test_workflow_pack_run_consumer_view_exposes_latest_review_transition(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-consumer-002"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.consumer.002",
            "reason": "Accepted for consumer view review metadata coverage.",
        },
    )
    assert review_response.status_code == 200

    consumer_view_response = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view")

    assert consumer_view_response.status_code == 200
    body = consumer_view_response.json()
    assert body["review"]["state"] == "ACCEPTED"
    assert body["review"]["latest_review_event_at"] is not None
    assert body["review"]["latest_review_actor"] == "review:banker.sg.consumer.002"
    assert body["review"]["review_transition_count"] == 1
    assert body["review"]["has_review_history"] is True
    assert body["provenance_summary"]["artifact_ref_count"] == 1
    assert "task_contract" in body["provenance_summary"]["evidence_types"]


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
    assert body["provenance"]["artifact_ref_count"] == 1
    assert body["provenance"]["artifact_types"] == ["run_output_summary"]
    assert body["provenance"]["evidence_descriptor_count"] >= 1
    assert "task_contract" in body["provenance"]["evidence_types"]
    assert body["artifact_ref_count"] == 1
    assert body["latest_event_type"] == "RUN_RECORDED"
    assert body["latest_event_actor"] == "lotus-ai.workflow-pack-run-ledger"
    assert body["latest_review_event_at"] is None
    assert body["latest_review_actor"] is None
    assert body["review_transition_count"] == 0
    assert body["event_type_counts"] == {"RUN_RECORDED": 1}
    assert any(finding["finding_id"] == "review_pending" for finding in body["findings"])


def test_workflow_pack_run_operator_profile_exposes_latest_review_transition(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-operator-002"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.operator.003",
            "reason": "Accepted for operator profile review metadata coverage.",
        },
    )
    assert review_response.status_code == 200

    profile_response = client.get(f"/platform/workflow-packs/runs/{run_id}/operator-profile")

    assert profile_response.status_code == 200
    body = profile_response.json()
    assert body["latest_event_type"] == "REVIEW_STATE_UPDATED"
    assert body["latest_review_event_at"] is not None
    assert body["latest_review_actor"] == "review:banker.sg.operator.003"
    assert body["review_transition_count"] == 1
    assert body["provenance"]["artifact_ref_count"] == 1
    assert "task_contract" in body["provenance"]["evidence_types"]


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
