"""API contract and SQL restart proof for the governed model catalogue (issue #175, slice 1)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import app
from app.services.model_catalogue_store import reset_model_catalogue_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings

APPROVED_INVENTORY_JSON = json.dumps(
    [
        {
            "provider_id": "text.openai",
            "provider_mode": "openai",
            "model_id": "gpt-5.2",
            "model_version": "gpt-5.2-2026-05-01",
            "workflow_pack_ids": ["advisor_brief.pack"],
            "approval_ref": "mrm-approval-2026-014",
            "approved_from_utc": "2026-05-01T00:00:00Z",
            "approved_until_utc": "2027-05-01T00:00:00Z",
        }
    ]
)


def test_model_catalogue_returns_seeded_identities_with_pinning_posture(
    client: TestClient,
) -> None:
    with override_runtime_settings(
        provider_mode="local_openai_compatible",
        live_text_provider_id="text.local",
        live_text_model_id="qwen3:8b",
        live_text_model_version=None,
        workflow_run_model_risk_inventory_json=APPROVED_INVENTORY_JSON,
    ):
        response = client.get("/platform/models/catalogue")

        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "lotus-ai"
        assert body["store_mode"] == "memory"
        assert body["entry_count"] == 2
        assert body["unpinned_revision_count"] == 1

        by_id = {entry["entry_id"]: entry for entry in body["entries"]}
        settings_entry = by_id["text.local:qwen3:8b"]
        assert settings_entry["lifecycle_state"] == "CATALOGUED"
        assert settings_entry["revision_pinned"] is False
        assert settings_entry["seed_source"] == "settings_live_text"
        assert settings_entry["approval_evidence_refs"] == []

        approved_entry = by_id["text.openai:gpt-5.2-2026-05-01"]
        assert approved_entry["lifecycle_state"] == "APPROVED"
        assert approved_entry["revision_pinned"] is True
        assert approved_entry["model_family"] == "gpt-5.2"
        assert approved_entry["approved_workflow_pack_ids"] == ["advisor_brief.pack"]
        assert approved_entry["approval_evidence_refs"] == ["mrm-approval-2026-014"]
        assert approved_entry["seed_source"] == "approved_workflow_run_model_inventory"


def test_model_catalogue_reads_are_stable_across_repeated_requests(
    client: TestClient,
) -> None:
    with override_runtime_settings(
        provider_mode="openai",
        live_text_provider_id="text.openai",
        live_text_model_id="gpt-5.2",
        live_text_model_version="gpt-5.2-2026-05-01",
        workflow_run_model_risk_inventory_json="[]",
    ):
        first = client.get("/platform/models/catalogue")
        second = client.get("/platform/models/catalogue")

        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()


def test_model_catalogue_survives_a_store_restart_in_sqlalchemy_mode(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'model-catalogue-restart.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        model_catalogue_store_mode="sqlalchemy",
        database_url=database_url,
        provider_mode="openai",
        live_text_provider_id="text.openai",
        live_text_model_id="gpt-5.2",
        live_text_model_version="gpt-5.2-2026-05-01",
        workflow_run_model_risk_inventory_json=APPROVED_INVENTORY_JSON,
    ):
        with TestClient(app) as first_process:
            first_body = first_process.get("/platform/models/catalogue").json()
        assert first_body["store_mode"] == "sqlalchemy"
        assert first_body["entry_count"] == 1

        # Restart: drop every in-process handle; truth must come back from SQL.
        reset_model_catalogue_store_cache()

        with TestClient(app) as second_process:
            second_body = second_process.get("/platform/models/catalogue").json()

        assert second_body == first_body
        assert second_body["entries"][0]["created_at"] == first_body["entries"][0]["created_at"], (
            "a restart must re-read the catalogued row, not re-create it"
        )


def test_operator_deprecation_refuses_live_execution_end_to_end(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The lifecycle producer chain: an operator transition to DEPRECATED must
    refuse the next live execution at the gateway with the bounded category and
    a recorded rejection."""

    database_url = f"sqlite:///{tmp_path / 'catalogue-deprecation.db'}"
    upgrade_database_to_head(database_url)

    class _LiveAdapter:
        def execute(self, request: object, *, config: object | None = None) -> object:
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
                    "provider_request_id": "req_lc_1",
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "estimated_cost_usd": None,
                    "rate_card_ref": None,
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
        model_catalogue_store_mode="sqlalchemy",
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
                    "correlation_id": "corr-lc-001",
                    "requested_by": "ops.user@lotus",
                    "tenant_id": "tenant-sg-001",
                },
                "context": {
                    "summary": "Explain rebalance outcome",
                    "payload": {"status": "BLOCKED"},
                    "source_refs": ["lotus-manage:run:reb_lc_1"],
                },
                "expected_output_label": "EXPLANATION_ONLY",
            }

            before = client.post("/ai/tasks/execute", json=execute_payload)
            assert before.status_code == 200

            transitioned = client.post(
                "/platform/models/catalogue/text.openai:gpt-5.4/lifecycle-transitions",
                json={
                    "to_state": "DEPRECATED",
                    "reason": "Vendor end-of-life announced; retire from live service.",
                },
                headers={"X-Caller-App": "lotus-platform"},
            )
            assert transitioned.status_code == 200
            assert transitioned.json()["entry"]["lifecycle_state"] == "DEPRECATED"
            # Identity comes from the authenticated caller, and the record is
            # honest that no approval existed (issue #245).
            transition_record = transitioned.json()["transition"]
            assert transition_record["requested_by"] == "lotus-platform (trusted_http_header)"
            assert transition_record["approved_by"] is None

            refused = client.post("/ai/tasks/execute", json=execute_payload)
            assert refused.status_code == 503
            assert "MODEL_LIFECYCLE_INELIGIBLE" in refused.text

            detail = client.get(
                "/platform/models/catalogue/text.openai:gpt-5.4",
                headers={"X-Caller-App": "lotus-platform"},
            )
            assert detail.status_code == 200
            events = detail.json()["lifecycle_events"]
            assert len(events) == 1
            assert events[0]["from_state"] == "CATALOGUED"
            assert events[0]["to_state"] == "DEPRECATED"

            unknown = client.get(
                "/platform/models/catalogue/text.unknown:nope",
                headers={"X-Caller-App": "lotus-platform"},
            )
            assert unknown.status_code == 404


def test_governed_promotion_flow_over_http(tmp_path: Path) -> None:
    """The governed two-step serving promotion end-to-end (issue #245):
    verified requester states the intent, a DISTINCT verified credential
    approves the exact hash, and the transition records the full evidence
    chain - while the single-call route refuses serving targets."""

    from tests.support.caller_credentials import (
        generate_caller_signing_key,
        mint_caller_credential,
        public_keys_setting,
    )

    requester_key = generate_caller_signing_key()
    approver_key = generate_caller_signing_key()
    requester_headers = {
        "Authorization": "Bearer "
        + mint_caller_credential(
            signing_key=requester_key,
            key_id="catalogue-ops-alpha",
            subject="lotus-platform",
            expires_in_seconds=3600,
        )
    }
    approver_headers = {
        "Authorization": "Bearer "
        + mint_caller_credential(
            signing_key=approver_key,
            key_id="catalogue-ops-beta",
            subject="lotus-platform",
            expires_in_seconds=3600,
        )
    }

    database_url = f"sqlite:///{tmp_path / 'catalogue-promotion.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        model_catalogue_store_mode="sqlalchemy",
        database_url=database_url,
        provider_mode="local_openai_compatible",
        live_text_provider_id="text.local",
        live_text_model_id="qwen3:8b",
        live_text_model_version=None,
        workflow_run_model_risk_inventory_json="[]",
        caller_trust_mode="verified_service_jwt",
        caller_jwt_issuer="https://platform.lotus/issuer",
        caller_jwt_audience="lotus-ai",
        caller_jwt_public_keys=public_keys_setting(
            **{"catalogue-ops-alpha": requester_key, "catalogue-ops-beta": approver_key}
        ),
    ):
        with TestClient(app) as client:
            from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
            from app.services.evaluation_runtime_store import get_evaluation_runtime_store

            get_evaluation_runtime_store().save_run(
                EvaluationRunRecord(
                    run_id="runtime_promotion_http_001",
                    fixture_id="model_promotion_examples",
                    manifest_version="foundation.v1",
                    lifecycle_status="COMPLETED",
                    triggered_by="operator-a",
                    submitted_at="2026-09-03T09:00:00Z",
                    async_job_id=None,
                    latest_message="Promotion evidence fixture.",
                    verdict="PASS",
                    case_count=3,
                )
            )
            entry_id = "text.local:qwen3:8b"
            base = f"/platform/models/catalogue/{entry_id}"

            # A catalogue read idempotently seeds the configured identity.
            seeded = client.get("/platform/models/catalogue", headers=requester_headers)
            assert seeded.status_code == 200

            evaluating = client.post(
                f"{base}/lifecycle-transitions",
                json={"to_state": "EVALUATING", "reason": "Begin evaluation."},
                headers=requester_headers,
            )
            assert evaluating.status_code == 200

            # The single-call route refuses a serving target outright.
            blocked = client.post(
                f"{base}/lifecycle-transitions",
                json={"to_state": "APPROVED", "reason": "Attempt ungoverned promotion."},
                headers=requester_headers,
            )
            assert blocked.status_code == 409
            assert "promotion-requests" in blocked.json()["detail"]

            pending = client.post(
                f"{base}/promotion-requests",
                json={
                    "to_state": "APPROVED",
                    "reason": "Passing evaluation evidence supports approval.",
                    "evaluation_run_id": "runtime_promotion_http_001",
                    "requested_by": "alice@lotus.test",
                },
                headers=requester_headers,
            )
            assert pending.status_code == 200
            action = pending.json()["governed_action"]
            assert action["status"] == "PENDING"

            # The requester's own credential cannot approve.
            same_credential = client.post(
                f"{base}/promotion-approvals",
                json={"action_id": action["action_id"], "action_hash": action["action_hash"]},
                headers=requester_headers,
            )
            assert same_credential.status_code == 403

            approved = client.post(
                f"{base}/promotion-approvals",
                json={
                    "action_id": action["action_id"],
                    "action_hash": action["action_hash"],
                    "approved_by": "bob@lotus.test",
                },
                headers=approver_headers,
            )
            assert approved.status_code == 200
            body = approved.json()
            assert body["entry"]["lifecycle_state"] == "APPROVED"
            assert (
                "evaluation-run:runtime_promotion_http_001"
                in (body["entry"]["approval_evidence_refs"])
            )
            assert body["transition"]["requested_by"] == (
                "lotus-platform (credential catalogue-ops-alpha)"
            )
            assert body["transition"]["approved_by"] == (
                "lotus-platform (credential catalogue-ops-beta)"
            )
            assert body["governed_action"]["status"] == "EXECUTED"


def test_capability_degrade_and_governed_restore_over_http(tmp_path: Path) -> None:
    """Capability-scoped degradation end-to-end (issue #245, slice 2): one
    verified principal degrades immediately; a DISTINCT verified credential
    approves the governed restore backed by PASS-verdict eval evidence."""

    from tests.support.caller_credentials import (
        generate_caller_signing_key,
        mint_caller_credential,
        public_keys_setting,
    )

    requester_key = generate_caller_signing_key()
    approver_key = generate_caller_signing_key()
    requester_headers = {
        "Authorization": "Bearer "
        + mint_caller_credential(
            signing_key=requester_key,
            key_id="capability-ops-alpha",
            subject="lotus-platform",
            expires_in_seconds=3600,
        )
    }
    approver_headers = {
        "Authorization": "Bearer "
        + mint_caller_credential(
            signing_key=approver_key,
            key_id="capability-ops-beta",
            subject="lotus-platform",
            expires_in_seconds=3600,
        )
    }

    database_url = f"sqlite:///{tmp_path / 'catalogue-capability.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        model_catalogue_store_mode="sqlalchemy",
        database_url=database_url,
        provider_mode="local_openai_compatible",
        live_text_provider_id="text.local",
        live_text_model_id="qwen3:8b",
        live_text_model_version=None,
        workflow_run_model_risk_inventory_json="[]",
        caller_trust_mode="verified_service_jwt",
        caller_jwt_issuer="https://platform.lotus/issuer",
        caller_jwt_audience="lotus-ai",
        caller_jwt_public_keys=public_keys_setting(
            **{"capability-ops-alpha": requester_key, "capability-ops-beta": approver_key}
        ),
    ):
        with TestClient(app) as client:
            from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
            from app.services.evaluation_runtime_store import get_evaluation_runtime_store

            get_evaluation_runtime_store().save_run(
                EvaluationRunRecord(
                    run_id="runtime_capability_http_001",
                    fixture_id="model_promotion_examples",
                    manifest_version="foundation.v1",
                    lifecycle_status="COMPLETED",
                    triggered_by="operator-a",
                    submitted_at="2026-09-03T10:00:00Z",
                    async_job_id=None,
                    latest_message="Capability restore evidence fixture.",
                    verdict="PASS",
                    case_count=3,
                )
            )
            base = "/platform/models/catalogue/text.local:qwen3:8b"

            seeded = client.get("/platform/models/catalogue", headers=requester_headers)
            assert seeded.status_code == 200

            degraded = client.post(
                f"{base}/capability-degradations",
                json={
                    "dimension": "supports_structured_output",
                    "reason": "Structured output failing contract validation.",
                },
                headers=requester_headers,
            )
            assert degraded.status_code == 200
            body = degraded.json()
            assert body["degradation"]["degraded_by"] == (
                "lotus-platform (credential capability-ops-alpha)"
            )
            assert "supports_structured_output" in body["entry"]["capability_degradations"]

            pending = client.post(
                f"{base}/capability-restore-requests",
                json={
                    "dimension": "supports_structured_output",
                    "reason": "Provider fixed the regression; run passes again.",
                    "evaluation_run_id": "runtime_capability_http_001",
                },
                headers=requester_headers,
            )
            assert pending.status_code == 200
            action = pending.json()["governed_action"]
            assert action["status"] == "PENDING"

            approved = client.post(
                f"{base}/capability-restore-approvals",
                json={"action_id": action["action_id"], "action_hash": action["action_hash"]},
                headers=approver_headers,
            )
            assert approved.status_code == 200
            restored = approved.json()
            assert restored["entry"]["capability_degradations"] == {}
            assert restored["governed_action"]["status"] == "EXECUTED"
            assert restored["governed_action"]["action_payload"]["degraded_by"] == (
                "lotus-platform (credential capability-ops-alpha)"
            )
