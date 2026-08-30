"""API contract, live enforcement and restart proof for kill switches (issue #177, slice 1)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import app
from app.services.kill_switch_store import reset_kill_switch_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings

CONTROL_HEADERS = {"X-Caller-App": "lotus-platform"}


def _activation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "caller_app": "lotus-platform",
        "scope": "TASK",
        "target": "explain.v1",
        "reason": "Incident LOTUS-4711: halt this task pending review.",
        "requested_by": "ops.primary@lotus",
        "approved_by": "ops.secondary@lotus",
    }
    payload.update(overrides)
    return payload


def test_kill_switch_lifecycle_enforces_and_restores_live_execution(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'kill-switch-api.db'}"
    upgrade_database_to_head(database_url)

    class _LiveAdapter:
        def execute(self, request: object) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": None,
                    "failure_category": None,
                    "timeout_ms": 4000,
                    "retry_count": 0,
                    "max_output_tokens": 512,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_ks_1",
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "estimated_cost_usd": None,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LiveAdapter(),
    )

    with override_runtime_settings(
        kill_switch_store_mode="sqlalchemy",
        database_url=database_url,
        provider_mode="openai",
        provider_rollout_state="CANARY_ENABLED",
        live_text_provider_id="text.openai",
        live_text_model_id="gpt-5.4",
        live_text_model_version=None,
        live_text_provider_api_key="secret",
        live_text_allowed_task_ids="explain.v1",
        live_text_quota_enforced=False,
        live_text_budget_enforced=False,
        live_text_degradation_enforced=False,
        workflow_run_model_risk_inventory_json="[]",
    ):
        with TestClient(app) as client:
            execute_payload = {
                "task_id": "explain.v1",
                "input_mode": "STRUCTURED_CONTEXT",
                "caller": {
                    "caller_app": "lotus-manage",
                    "correlation_id": "corr-ks-001",
                    "requested_by": "ops.user@lotus",
                    "tenant_id": "tenant-sg-001",
                },
                "context": {
                    "summary": "Explain rebalance outcome",
                    "payload": {"status": "BLOCKED"},
                    "source_refs": ["lotus-manage:run:reb_ks_1"],
                },
                "expected_output_label": "EXPLANATION_ONLY",
            }

            before = client.post("/ai/tasks/execute", json=execute_payload)
            assert before.status_code == 200

            activated = client.post(
                "/platform/providers/kill-switches",
                json=_activation_payload(),
                headers=CONTROL_HEADERS,
            )
            assert activated.status_code == 200
            switch_id = activated.json()["activation"]["switch_id"]
            assert activated.json()["store_mode"] == "sqlalchemy"

            refused = client.post("/ai/tasks/execute", json=execute_payload)
            assert refused.status_code == 503
            assert "KILL_SWITCH_ACTIVE" in refused.text
            assert switch_id in refused.text

            status_body = client.get(
                "/platform/providers/kill-switches", headers=CONTROL_HEADERS
            ).json()
            assert status_body["active_count"] == 1

            cleared = client.post(
                f"/platform/providers/kill-switches/{switch_id}/clear",
                json={
                    "caller_app": "lotus-platform",
                    "reason": "Incident resolved.",
                    "requested_by": "ops.primary@lotus",
                    "approved_by": "ops.secondary@lotus",
                },
                headers=CONTROL_HEADERS,
            )
            assert cleared.status_code == 200

            restored = client.post("/ai/tasks/execute", json=execute_payload)
            assert restored.status_code == 200


def test_kill_switch_activations_survive_a_store_restart(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'kill-switch-restart.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        kill_switch_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as first_process:
            activated = first_process.post(
                "/platform/providers/kill-switches",
                json=_activation_payload(scope="TENANT", target="tenant-sg-001"),
                headers=CONTROL_HEADERS,
            )
            assert activated.status_code == 200

        # Restart: drop every in-process handle; truth must come back from SQL.
        reset_kill_switch_store_cache()

        with TestClient(app) as second_process:
            status_body = second_process.get(
                "/platform/providers/kill-switches", headers=CONTROL_HEADERS
            ).json()

        assert status_body["active_count"] == 1
        assert status_body["activations"][0]["scope"] == "TENANT"
        assert status_body["activations"][0]["target"] == "tenant-sg-001"


def test_unauthorized_caller_cannot_activate(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'kill-switch-authz.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        kill_switch_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as client:
            response = client.post(
                "/platform/providers/kill-switches",
                json=_activation_payload(caller_app="lotus-manage"),
                headers={"X-Caller-App": "lotus-manage"},
            )
            assert response.status_code == 403
            assert (
                client.get("/platform/providers/kill-switches", headers=CONTROL_HEADERS).json()[
                    "active_count"
                ]
                == 0
            )
