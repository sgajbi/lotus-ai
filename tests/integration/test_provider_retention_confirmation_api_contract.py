import base64
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.config import settings
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from tests.support.workflow_pack_fixtures import (
    idea_explanation_workflow_pack_execution_request_json,
)


def test_provider_retention_confirmation_api_is_tenant_bound_and_idempotent(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=idea_explanation_workflow_pack_execution_request_json(
            correlation_id="corr-provider-retention-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = execute_response.json()["workflow_pack_run"]["run_id"]
    repository = get_workflow_pack_run_store()
    run = repository.get_run(run_id=run_id)
    assert run is not None
    repository.save_run(
        replace(
            run,
            tenant_id="tenant-sg-001",
            provider_mode="openai",
            provider_id="text.openai",
            model_id="gpt-5.4",
            model_version="2026-06-01",
            stubbed=False,
        )
    )
    _configure_key(monkeypatch)
    headers = {
        "Idempotency-Key": "provider-retention-api-001",
        "X-Caller-App": "lotus-ai-provider-operations",
        "X-Tenant-Id": "tenant-sg-001",
    }
    payload = _payload()

    first = client.post(
        f"/platform/provider-operations/workflow-runs/{run_id}/retention-confirmations",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/platform/provider-operations/workflow-runs/{run_id}/retention-confirmations",
        json=payload,
        headers=headers,
    )
    wrong_tenant = client.post(
        f"/platform/provider-operations/workflow-runs/{run_id}/retention-confirmations",
        json=payload,
        headers={**headers, "Idempotency-Key": "wrong-tenant", "X-Tenant-Id": "tenant-other"},
    )
    conflict = client.post(
        f"/platform/provider-operations/workflow-runs/{run_id}/retention-confirmations",
        json={**payload, "provider_confirmation_ref": "provider-confirmation-changed"},
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.json() == first.json()
    assert first.json()["claims"]["provider_id"] == "text.openai"
    assert first.json()["claims"]["tenant_id"] == "tenant-sg-001"
    assert first.json()["claims"]["deletion_confirmed"] is True
    assert first.json()["claims"]["raw_prompt_included"] is False
    assert first.json()["claims"]["raw_output_included"] is False
    assert first.json()["claims"]["client_identifier_included"] is False
    assert wrong_tenant.status_code == 409
    assert wrong_tenant.json()["metadata"]["reason_code"] == "tenant_mismatch"
    assert conflict.status_code == 409
    assert conflict.json()["metadata"]["reason_code"] == "idempotency_conflict"
    for forbidden in ("pb_sg_global_bal_001", "client-name", "sk-test-secret"):
        assert forbidden not in first.text.lower()


def _configure_key(monkeypatch: MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    encoded = base64.urlsafe_b64encode(private_key.private_bytes_raw()).rstrip(b"=").decode()
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", "attestation-key-2026-07")
    monkeypatch.setattr(settings, "workflow_run_attestation_rotation_epoch", 1)
    monkeypatch.setattr(settings, "workflow_run_attestation_private_key_base64url", encoded)
    monkeypatch.setattr(
        settings,
        "workflow_run_attestation_key_not_before_utc",
        "2026-07-01T00:00:00Z",
    )


def _payload() -> dict[str, object]:
    return {
        "provider_confirmation_ref": "provider-confirmation-001",
        "retention_policy_id": "idea-provider-zero-retention-v1",
        "outcome": "DELETION_CONFIRMED",
        "provider_decision_at_utc": "2026-07-12T01:59:00Z",
        "evidence_sha256": "e" * 64,
    }
