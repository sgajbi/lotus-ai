from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_prompt_registry_routes(client: TestClient) -> None:
    list_response = client.get("/platform/prompts")
    assert list_response.status_code == 200
    assert any(prompt["task_id"] == "explain.v1" for prompt in list_response.json())
    assert any(prompt["lifecycle_status"] == "CANDIDATE" for prompt in list_response.json())

    detail_response = client.get("/platform/prompts/explain.v1")
    assert detail_response.status_code == 200
    assert detail_response.json()["prompt_version"] == "foundation.explain.v1"
    assert detail_response.json()["management_mode"] == "SEEDED_MEMORY"


def test_prompt_governance_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/governance")

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_store_mode"] == "memory"
    assert body["management_mode"] == "SEEDED_MEMORY"
    assert body["runtime_mutation_enabled"] is False
    assert body["promotion_write_api_enabled"] is False
    assert body["control_history_endpoint"] == "/platform/prompts/control-history"
    assert "governed promote and rollback actions" in body["promotion_path"]
    assert body["active_prompt_count"] >= 7


def test_prompt_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["prompt_store_mode"] == "memory"
    assert body["selection_mode"] == "ROLLOUT_STATE_ACTIVE"
    assert body["rollout_mode"] == "GOVERNED_CONTROL_ACTIONS"
    assert body["candidate_prompt_count"] == 0
    assert any(selection["task_id"] == "explain.v1" for selection in body["selections"])
    assert body["selections"][0]["rollout_role"] == "ACTIVE"
    assert any(state["task_id"] == "explain.v1" for state in body["rollout_states"])


def test_prompt_control_routes(client: TestClient) -> None:
    history_response = client.get("/platform/prompts/control-history")
    assert history_response.status_code == 200
    assert history_response.json()["supported_action_types"] == [
        "PROMOTE_CANDIDATE",
        "ROLLBACK_TO_PREVIOUS_ACTIVE",
    ]

    blocked_promote_response = client.post(
        "/platform/prompts/control-actions",
        json={
            "task_id": "explain.v1",
            "action_type": "PROMOTE_CANDIDATE",
            "caller_app": "lotus-platform",
            "candidate_prompt_version": "foundation.explain.v2",
            "requested_by": "alice@lotus.test",
            "approved_by": "bob@lotus.test",
            "reason": "Attempt promotion without prompt approval evidence",
        },
    )
    assert blocked_promote_response.status_code == 409
    assert "SQL-backed prompt rollout state" in blocked_promote_response.json()["detail"]


def test_prompt_control_routes_support_sql_backed_durable_actions(tmp_path: Path) -> None:
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    database_url = f"sqlite:///{tmp_path / 'prompt-api-contract.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
                get_evaluation_runtime_store().save_run(
                    EvaluationRunRecord(
                        run_id=f"runtime_prompt_gate_{fixture_id}",
                        fixture_id=fixture_id,
                        manifest_version="foundation.v1",
                        lifecycle_status="COMPLETED",
                        triggered_by="operator-a",
                        submitted_at="2026-03-23T12:00:00Z",
                        async_job_id=f"async_prompt_gate_{fixture_id}",
                        latest_message="Prompt rollout approval fixture passed.",
                        verdict="PASS",
                        case_count=1,
                    )
                )

            promote_response = durable_client.post(
                "/platform/prompts/control-actions",
                json={
                    "task_id": "explain.v1",
                    "action_type": "PROMOTE_CANDIDATE",
                    "caller_app": "lotus-platform",
                    "candidate_prompt_version": "foundation.explain.v2",
                    "requested_by": "alice@lotus.test",
                    "approved_by": "bob@lotus.test",
                    "reason": "Approve explanation candidate",
                },
            )
            assert promote_response.status_code == 200
            assert (
                promote_response.json()["rollout_state"]["active_prompt_version"]
                == "foundation.explain.v2"
            )
            assert (
                promote_response.json()["rollout_state"]["latest_control_event"]["action_type"]
                == "PROMOTE_CANDIDATE"
            )
            assert (
                promote_response.json()["event"]["authorization"]["caller_app"] == "lotus-platform"
            )

            runtime_response = durable_client.get("/platform/prompts/runtime-status")
            assert runtime_response.status_code == 200
            explain_state = next(
                state
                for state in runtime_response.json()["rollout_states"]
                if state["task_id"] == "explain.v1"
            )
            assert explain_state["latest_control_event"]["action_type"] == "PROMOTE_CANDIDATE"

            rollback_response = durable_client.post(
                "/platform/prompts/control-actions",
                json={
                    "task_id": "explain.v1",
                    "action_type": "ROLLBACK_TO_PREVIOUS_ACTIVE",
                    "caller_app": "lotus-platform",
                    "requested_by": "alice@lotus.test",
                    "approved_by": "bob@lotus.test",
                    "reason": "Restore known-good prompt",
                },
            )
            assert rollback_response.status_code == 200
            assert (
                rollback_response.json()["rollout_state"]["active_prompt_version"]
                == "foundation.explain.v1"
            )

            task_history_response = durable_client.get(
                "/platform/prompts/control-history", params={"task_id": "explain.v1"}
            )
            assert task_history_response.status_code == 200
            assert len(task_history_response.json()["latest_events"]) == 2
            assert task_history_response.json()["latest_events"][0]["action_type"] == (
                "ROLLBACK_TO_PREVIOUS_ACTIVE"
            )
            assert (
                task_history_response.json()["latest_events"][0]["authorization"]["caller_app"]
                == "lotus-platform"
            )


def test_prompt_control_history_route_rejects_oversized_limit(client: TestClient) -> None:
    response = client.get("/platform/prompts/control-history", params={"limit": 201})

    assert response.status_code == 422


def test_prompt_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["prompt_store_mode"] == "memory"
    assert body["management_mode"] == "SEEDED_MEMORY"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 1
    assert len(body["activation_path"]) == 4


def test_prompt_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is True
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 4
    assert body["items"][0]["runbook_id"] == "prompt_operational_runbook"
    assert body["items"][1]["status"] == "READY"


def test_prompt_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 2
    assert body["items"][0]["evidence_id"] == "prompt_fixture_coverage_pack"
    assert body["items"][1]["status"] == "FOUNDATION_STAGED"
    assert body["approval_gate"]["domain_id"] == "prompt_rollout"


def test_prompt_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 2
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is True
    assert body["evidence_readiness"]["evidence_ready"] is False
    assert len(body["governance_summary"]) == 3


def test_prompt_control_routes_block_unauthorized_caller(tmp_path: Path) -> None:
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    database_url = f"sqlite:///{tmp_path / 'prompt-api-unauthorized.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
                get_evaluation_runtime_store().save_run(
                    EvaluationRunRecord(
                        run_id=f"runtime_prompt_unauthorized_{fixture_id}",
                        fixture_id=fixture_id,
                        manifest_version="foundation.v1",
                        lifecycle_status="COMPLETED",
                        triggered_by="operator-a",
                        submitted_at="2026-03-23T12:00:00Z",
                        async_job_id=f"async_prompt_unauthorized_{fixture_id}",
                        latest_message="Prompt rollout approval fixture passed.",
                        verdict="PASS",
                        case_count=1,
                    )
                )

            blocked_response = durable_client.post(
                "/platform/prompts/control-actions",
                json={
                    "task_id": "explain.v1",
                    "action_type": "PROMOTE_CANDIDATE",
                    "caller_app": "lotus-workbench",
                    "candidate_prompt_version": "foundation.explain.v2",
                    "requested_by": "alice@lotus.test",
                    "approved_by": "bob@lotus.test",
                    "reason": "Unauthorized promotion attempt",
                },
            )
            assert blocked_response.status_code == 403
