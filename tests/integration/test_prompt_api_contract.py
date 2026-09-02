from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.caller_credentials import (
    generate_caller_signing_key,
    mint_caller_credential,
    public_keys_setting,
)


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


# Two real EdDSA credentials for the governed promotion flow (issue #157): a
# requester and an approver under DISTINCT signing keys, both authenticating
# as the platform control caller.
_REQUESTER_KEY = generate_caller_signing_key()
_APPROVER_KEY = generate_caller_signing_key()
_PUBLIC_KEYS = public_keys_setting(
    **{"prompt-ops-alpha": _REQUESTER_KEY, "prompt-ops-beta": _APPROVER_KEY}
)
_REQUESTER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_REQUESTER_KEY,
        key_id="prompt-ops-alpha",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}
_APPROVER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_APPROVER_KEY,
        key_id="prompt-ops-beta",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}


def test_prompt_control_routes(client: TestClient) -> None:
    history_response = client.get("/platform/prompts/control-history")
    assert history_response.status_code == 200
    assert history_response.json()["supported_action_types"] == [
        "PROMOTE_CANDIDATE",
        "ROLLBACK_TO_PREVIOUS_ACTIVE",
    ]

    # Promotion through the single-call route is refused with guidance to the
    # governed two-step flow (issue #157) - after authorization, like every
    # other action-shape check.
    blocked_promote_response = client.post(
        "/platform/prompts/control-actions",
        json={
            "task_id": "explain.v1",
            "action_type": "PROMOTE_CANDIDATE",
            "caller_app": "lotus-platform",
            "candidate_prompt_version": "foundation.explain.v2",
            "requested_by": "alice@lotus.test",
            "approved_by": "bob@lotus.test",
            "reason": "Attempt promotion via the ungoverned route",
        },
    )
    assert blocked_promote_response.status_code == 409
    assert "governed action" in blocked_promote_response.json()["detail"]
    assert "promote-requests" in blocked_promote_response.json()["detail"]

    # The governed request step still requires the durable control plane.
    blocked_intent_response = client.post(
        "/platform/prompts/promote-requests",
        json={
            "task_id": "explain.v1",
            "candidate_prompt_version": "foundation.explain.v2",
            "reason": "Attempt promotion without a durable prompt store",
        },
    )
    assert blocked_intent_response.status_code == 409
    assert "SQL-backed prompt rollout state" in blocked_intent_response.json()["detail"]


def test_prompt_control_routes_support_sql_backed_durable_actions(tmp_path: Path) -> None:
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    database_url = f"sqlite:///{tmp_path / 'prompt-api-contract.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
        caller_trust_mode="verified_service_jwt",
        caller_jwt_issuer="https://platform.lotus/issuer",
        caller_jwt_audience="lotus-ai",
        caller_jwt_public_keys=_PUBLIC_KEYS,
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

            # Governed promotion over HTTP (issue #157): the request step
            # parks the intent under the requester's verified credential and
            # the active prompt is unchanged until a DISTINCT credential
            # approves the exact hash.
            pending_response = durable_client.post(
                "/platform/prompts/promote-requests",
                json={
                    "task_id": "explain.v1",
                    "candidate_prompt_version": "foundation.explain.v2",
                    "reason": "Approve explanation candidate",
                    "requested_by": "alice@lotus.test",
                },
                headers=_REQUESTER_HEADERS,
            )
            assert pending_response.status_code == 200
            pending_action = pending_response.json()["governed_action"]
            assert pending_action["status"] == "PENDING"
            assert pending_action["requester_key_id"] == "prompt-ops-alpha"

            self_approval = durable_client.post(
                "/platform/prompts/promote-approvals",
                json={
                    "task_id": "explain.v1",
                    "action_id": pending_action["action_id"],
                    "action_hash": pending_action["action_hash"],
                },
                headers=_REQUESTER_HEADERS,
            )
            assert self_approval.status_code == 403

            promote_response = durable_client.post(
                "/platform/prompts/promote-approvals",
                json={
                    "task_id": "explain.v1",
                    "action_id": pending_action["action_id"],
                    "action_hash": pending_action["action_hash"],
                    "approved_by": "bob@lotus.test",
                },
                headers=_APPROVER_HEADERS,
            )
            assert promote_response.status_code == 200
            assert (
                promote_response.json()["rollout_state"]["active_prompt_version"]
                == "foundation.explain.v2"
            )
            evidence = promote_response.json()["governed_action"]
            assert evidence["status"] == "EXECUTED"
            assert evidence["requester_key_id"] == "prompt-ops-alpha"
            assert evidence["approver_key_id"] == "prompt-ops-beta"

            explain_status = durable_client.get(
                "/platform/prompts/runtime-status", headers=_REQUESTER_HEADERS
            )
            assert explain_status.status_code == 200
            explain_state = next(
                state
                for state in explain_status.json()["rollout_states"]
                if state["task_id"] == "explain.v1"
            )
            assert explain_state["active_prompt_version"] == "foundation.explain.v2"
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
                headers=_REQUESTER_HEADERS,
            )
            assert rollback_response.status_code == 200
            assert (
                rollback_response.json()["rollout_state"]["active_prompt_version"]
                == "foundation.explain.v1"
            )

            task_history_response = durable_client.get(
                "/platform/prompts/control-history",
                params={"task_id": "explain.v1"},
                headers=_REQUESTER_HEADERS,
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
            # The promotion event records verified credential identities, not
            # the caller-typed names - those live on the governed action as
            # unverified attribution.
            promotion_event = task_history_response.json()["latest_events"][1]
            assert promotion_event["action_type"] == "PROMOTE_CANDIDATE"
            assert "prompt-ops-alpha" in promotion_event["requested_by"]
            assert "prompt-ops-beta" in promotion_event["approved_by"]


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
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "prompt_operational_runbook"
    assert body["items"][1]["status"] == "DOCUMENTED_ONLY"


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
    assert body["blocking_area_count"] == 3
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
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
