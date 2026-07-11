import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.config import settings


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
