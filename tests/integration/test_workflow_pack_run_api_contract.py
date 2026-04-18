from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


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
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-gateway",
                "correlation_id": "corr-pack-run-api-001",
            },
            "context": {
                "summary": "Draft advisor brief from source performance facts.",
                "payload": {
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                "source_refs": ["lotus-gateway:performance-summary:YTD"],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
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

    detail_response = client.get(f"/platform/workflow-packs/runs/{run['run_id']}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["run_id"] == run["run_id"]
    assert detail_body["events"][0]["event_type"] == "RUN_RECORDED"


def test_workflow_pack_run_detail_rejects_unknown_run(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/unknown-run")

    assert response.status_code == 404


def test_workflow_pack_run_review_action_updates_review_state(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-gateway",
                "correlation_id": "corr-pack-run-api-review-001",
            },
            "context": {
                "summary": "Draft advisor brief from source performance facts.",
                "payload": {
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                "source_refs": ["lotus-gateway:performance-summary:YTD"],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
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
    assert review_body["events"][0]["event_type"] == "REVIEW_STATE_UPDATED"
    detail_response = client.get(f"/platform/workflow-packs/runs/{run_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["run"]["review_state"] == "ACCEPTED"


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
                json={
                    "task_id": "explain.v1",
                    "input_mode": "STRUCTURED_CONTEXT",
                    "caller": {
                        "caller_app": "lotus-gateway",
                        "correlation_id": "corr-pack-run-api-sql-001",
                    },
                    "context": {
                        "summary": "Draft advisor brief from source performance facts.",
                        "payload": {
                            "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                            "period": {"period": "YTD"},
                            "performance": {
                                "portfolio_return_pct": 1.25,
                                "benchmark_return_pct": 7.93,
                                "active_return_pct": -6.68,
                            },
                            "supportability": [{"key": "portfolio_context", "value": "ready"}],
                        },
                        "source_refs": ["lotus-gateway:performance-summary:YTD"],
                    },
                    "expected_output_label": "EXPLANATION_ONLY",
                },
            )
            assert execute_response.status_code == 200

            catalog_response = client.get("/platform/workflow-packs/runs")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["run_store_mode"] == "sqlalchemy"
    assert catalog_body["run_count"] == 1
