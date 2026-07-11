from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.contracts.workflow_run_attestation import (
    WorkflowRunAttestationClaims,
    WorkflowRunAttestationEnvelope,
    WorkflowRunAttestationKeyDiscoveryResponse,
    WorkflowRunAttestationPublicKey,
)
from app.providers.ed25519_workflow_run_signer import Ed25519WorkflowRunAttestationSigner
from app.services.workflow_run_attestation_signing import sign_workflow_run_attestation
from app.services.workflow_run_attestation_verification import verify_workflow_run_attestation


NOW = datetime(2026, 7, 11, 10, tzinfo=UTC)


def _claims(**overrides: object) -> WorkflowRunAttestationClaims:
    values = {
        "schema_version": "lotus-ai.workflow-run-attestation.v1",
        "issuer": "lotus-ai",
        "audience": "lotus-idea",
        "run_id": "run-1",
        "consumer_request_id": "request-1",
        "replay_nonce": "a" * 64,
        "workflow_pack_id": "idea_explanation.pack",
        "workflow_pack_version": "v1",
        "registration_ref": "workflow-pack://idea/v1",
        "evaluator_id": "idea-explanation-guardrails",
        "evaluator_policy_version": "idea-policy.v1",
        "provider_id": "openai",
        "provider_mode": "live",
        "model_id": "gpt-5.4",
        "model_version": "2026-06-01",
        "model_risk_status": "approved",
        "input_evidence_sha256": "b" * 64,
        "output_content_sha256": "c" * 64,
        "issued_at_utc": NOW.isoformat().replace("+00:00", "Z"),
        "execution_started_at_utc": (NOW - timedelta(seconds=2)).isoformat(),
        "execution_completed_at_utc": (NOW - timedelta(seconds=1)).isoformat(),
        "expires_at_utc": (NOW + timedelta(minutes=5)).isoformat(),
        "stubbed": False,
        "supportability_status": "READY",
    }
    values.update(overrides)
    return WorkflowRunAttestationClaims.model_validate(values)


def _public_key(
    private_key: Ed25519PrivateKey, *, status: str = "active"
) -> WorkflowRunAttestationPublicKey:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return WorkflowRunAttestationPublicKey(
        key_id="key-1",
        algorithm="EdDSA",
        curve="Ed25519",
        public_key_base64url=base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"),
        rotation_epoch=1,
        status=status,
        not_before_utc=(NOW - timedelta(days=1)).isoformat(),
        not_after_utc=(NOW + timedelta(days=1)).isoformat(),
    )


def _signed(
    private_key: Ed25519PrivateKey, **claim_overrides: object
) -> WorkflowRunAttestationEnvelope:
    return sign_workflow_run_attestation(
        claims=_claims(**claim_overrides),
        signer=Ed25519WorkflowRunAttestationSigner(
            private_key=private_key, key_id="key-1", rotation_epoch=1
        ),
    )


def _discovery(key: WorkflowRunAttestationPublicKey) -> WorkflowRunAttestationKeyDiscoveryResponse:
    return WorkflowRunAttestationKeyDiscoveryResponse(
        schema_version="lotus-ai.workflow-run-attestation-keys.v1", issuer="lotus-ai", keys=[key]
    )


@pytest.mark.parametrize("status", ["active", "rotated"])
def test_active_and_rotated_keys_verify(status: str) -> None:
    private_key = Ed25519PrivateKey.generate()
    verify_workflow_run_attestation(
        envelope=_signed(private_key),
        key_discovery=_discovery(_public_key(private_key, status=status)),
        expected_audience="lotus-idea",
        verified_at_utc=NOW + timedelta(seconds=1),
    )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("revoked", "revoked"),
        ("unknown", "unknown or ambiguous"),
        ("audience", "audience"),
        ("expired", "not currently valid"),
        ("signature", "signature verification failed"),
    ],
)
def test_verification_fails_closed(case: str, message: str) -> None:
    private_key = Ed25519PrivateKey.generate()
    envelope = _signed(private_key)
    key = _public_key(private_key, status="revoked" if case == "revoked" else "active")
    discovery = _discovery(key)
    expected_audience = "other" if case == "audience" else "lotus-idea"
    verified_at = NOW + timedelta(minutes=6) if case == "expired" else NOW + timedelta(seconds=1)
    if case == "unknown":
        discovery.keys[0].key_id = "other-key"
    if case == "signature":
        discovery = _discovery(_public_key(Ed25519PrivateKey.generate()))

    with pytest.raises(ValueError, match=message):
        verify_workflow_run_attestation(
            envelope=envelope,
            key_discovery=discovery,
            expected_audience=expected_audience,
            verified_at_utc=verified_at,
        )
