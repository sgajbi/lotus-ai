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


def _encoded_private_key() -> str:
    return (
        base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw())
        .rstrip(b"=")
        .decode("ascii")
    )


def test_workflow_run_attestation_key_discovery_exposes_public_key_contract(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", "attestation-key-2026-07")
    monkeypatch.setattr(settings, "workflow_run_attestation_rotation_epoch", 1)
    monkeypatch.setattr(
        settings, "workflow_run_attestation_private_key_base64url", _encoded_private_key()
    )
    monkeypatch.setattr(
        settings, "workflow_run_attestation_key_not_before_utc", "2026-07-11T00:00:00Z"
    )
    monkeypatch.setattr(settings, "workflow_run_attestation_key_not_after_utc", None)
    monkeypatch.setattr(settings, "workflow_run_attestation_rotated_public_keys_json", "[]")

    response = client.get("/.well-known/lotus-ai-workflow-attestation-keys")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "lotus-ai.workflow-run-attestation-keys.v1"
    assert body["issuer"] == "lotus-ai"
    assert body["keys"][0]["key_id"] == "attestation-key-2026-07"
    assert body["keys"][0]["status"] == "active"
    assert body["keys"][0]["algorithm"] == "EdDSA"
    assert body["keys"][0]["curve"] == "Ed25519"
    assert "private" not in response.text.lower()


def test_workflow_run_attestation_key_discovery_fails_closed_without_key(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", None)
    monkeypatch.setattr(settings, "workflow_run_attestation_rotation_epoch", None)
    monkeypatch.setattr(settings, "workflow_run_attestation_private_key_base64url", None)

    response = client.get("/.well-known/lotus-ai-workflow-attestation-keys")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == "LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEYS_UNAVAILABLE"


def test_workflow_run_attestation_endpoint_returns_signed_approved_run(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=idea_explanation_workflow_pack_execution_request_json(
            correlation_id="corr-attestation-endpoint-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = execute_response.json()["workflow_pack_run"]["run_id"]
    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-idea",
            "reviewed_by": "idea-reviewer.sg.001",
            "reason": "Accepted for signed attestation contract verification.",
        },
    )
    assert review_response.status_code == 200
    repository = get_workflow_pack_run_store()
    run = repository.get_run(run_id=run_id)
    assert run is not None
    repository.save_run(
        replace(
            run,
            provider_mode="openai",
            provider_id="text.openai",
            model_id="gpt-5.4",
            model_version="2026-06-01",
            model_risk_status="approved",
            model_risk_approval_ref="model-risk://lotus-ai/gpt-5.4/2026-06-01",
            stubbed=False,
        )
    )
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", "attestation-key-2026-07")
    monkeypatch.setattr(settings, "workflow_run_attestation_rotation_epoch", 1)
    monkeypatch.setattr(
        settings, "workflow_run_attestation_private_key_base64url", _encoded_private_key()
    )
    monkeypatch.setattr(
        settings, "workflow_run_attestation_key_not_before_utc", "2026-07-11T00:00:00Z"
    )

    response = client.get(f"/platform/workflow-packs/runs/{run_id}/attestation")

    assert response.status_code == 200
    body = response.json()
    assert body["claims"]["run_id"] == run_id
    assert body["claims"]["audience"] == "lotus-idea"
    assert body["claims"]["model_risk_status"] == "approved"
    assert body["claims"]["stubbed"] is False
    assert body["signature"]["key_id"] == "attestation-key-2026-07"
    assert body["key_discovery_path"] == "/.well-known/lotus-ai-workflow-attestation-keys"
    for forbidden in ("idea_high_cash_001", "PB_SG_GLOBAL_BAL_001", "raw_prompt"):
        assert forbidden not in response.text


def test_workflow_run_attestation_endpoint_reports_unknown_run_before_key_configuration(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", None)
    monkeypatch.setattr(settings, "workflow_run_attestation_private_key_base64url", None)

    response = client.get("/platform/workflow-packs/runs/missing/attestation")

    assert response.status_code == 404
    assert response.json()["error_code"] == "LOTUS_AI_WORKFLOW_PACK_RUN_NOT_FOUND"
