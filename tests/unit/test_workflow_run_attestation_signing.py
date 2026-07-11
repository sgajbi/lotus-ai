from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import json

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.contracts.workflow_run_attestation import WorkflowRunAttestationClaims
from app.providers.ed25519_workflow_run_signer import Ed25519WorkflowRunAttestationSigner
from app.services.workflow_run_attestation_signing import (
    WorkflowRunSignature,
    canonical_attestation_payload,
    sign_workflow_run_attestation,
)


NOW = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)


def _claims(**overrides: object) -> WorkflowRunAttestationClaims:
    values: dict[str, object] = {
        "schema_version": "lotus-ai.workflow-run-attestation.v1",
        "issuer": "lotus-ai",
        "audience": "lotus-idea",
        "run_id": "run-001",
        "consumer_request_id": "idea-request-001",
        "replay_nonce": "a" * 64,
        "workflow_pack_id": "idea_explanation.pack",
        "workflow_pack_version": "v1",
        "registration_ref": "workflow-pack://idea_explanation.pack/v1",
        "evaluator_id": "idea-explanation-guardrails",
        "evaluator_policy_version": "idea-explanation-policy.v1",
        "provider_id": "openai",
        "provider_mode": "live",
        "model_id": "gpt-5.4",
        "model_version": "2026-06-01",
        "model_risk_status": "approved",
        "model_risk_approval_ref": "model-risk://lotus-ai/gpt-5.4/2026-06-01",
        "input_evidence_sha256": "b" * 64,
        "output_content_sha256": "c" * 64,
        "issued_at_utc": NOW.isoformat().replace("+00:00", "Z"),
        "execution_started_at_utc": (NOW - timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
        "execution_completed_at_utc": (NOW - timedelta(seconds=1))
        .isoformat()
        .replace("+00:00", "Z"),
        "expires_at_utc": (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "stubbed": False,
        "supportability_status": "READY",
    }
    values.update(overrides)
    return WorkflowRunAttestationClaims.model_validate(values)


def test_ed25519_signature_verifies_exact_canonical_claims() -> None:
    private_key = Ed25519PrivateKey.generate()
    claims = _claims()
    envelope = sign_workflow_run_attestation(
        claims=claims,
        signer=Ed25519WorkflowRunAttestationSigner(
            private_key=private_key, key_id="workflow-attestation-2026-07", rotation_epoch=1
        ),
    )

    signature = base64.urlsafe_b64decode(
        envelope.signature.signature_base64url
        + "=" * (-len(envelope.signature.signature_base64url) % 4)
    )
    private_key.public_key().verify(signature, canonical_attestation_payload(claims))
    assert envelope.signature.algorithm == "EdDSA"
    assert envelope.signature.key_id == "workflow-attestation-2026-07"
    assert envelope.key_discovery_path.startswith("/.well-known/")


def test_canonical_payload_is_order_stable_and_source_safe() -> None:
    first = canonical_attestation_payload(_claims())
    second = canonical_attestation_payload(
        WorkflowRunAttestationClaims.model_validate(
            dict(reversed(list(_claims().model_dump().items())))
        )
    )

    assert first == second
    assert first == json.dumps(
        json.loads(first), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    for forbidden in (b"prompt", b"portfolio", b"candidate", b"client", b"tenant", b"payload"):
        assert forbidden not in first.lower()


@pytest.mark.parametrize(
    "mutated_claim",
    [
        {"run_id": "run-002"},
        {"consumer_request_id": "idea-request-002"},
        {"workflow_pack_id": "other.pack"},
        {"input_evidence_sha256": "d" * 64},
        {"output_content_sha256": "d" * 64},
        {"model_id": "other-model"},
        {"model_version": "2026-06-02"},
    ],
)
def test_signature_rejects_mutated_governed_claim(mutated_claim: dict[str, object]) -> None:
    private_key = Ed25519PrivateKey.generate()
    claims = _claims()
    envelope = sign_workflow_run_attestation(
        claims=claims,
        signer=Ed25519WorkflowRunAttestationSigner(
            private_key=private_key, key_id="key-1", rotation_epoch=1
        ),
    )
    signature = base64.urlsafe_b64decode(
        envelope.signature.signature_base64url
        + "=" * (-len(envelope.signature.signature_base64url) % 4)
    )

    with pytest.raises(InvalidSignature):
        private_key.public_key().verify(
            signature,
            canonical_attestation_payload(_claims(**mutated_claim)),
        )


def test_claim_contract_rejects_unapproved_model_risk_posture() -> None:
    with pytest.raises(ValueError):
        _claims(model_risk_status="approval_unverified")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"execution_completed_at_utc": (NOW - timedelta(seconds=3)).isoformat()}, "completion"),
        ({"issued_at_utc": (NOW - timedelta(seconds=3)).isoformat()}, "issue time"),
        ({"expires_at_utc": NOW.isoformat()}, "expiry"),
        ({"issued_at_utc": "2026-07-11T10:00:00"}, "timezone-aware"),
    ],
)
def test_signing_rejects_invalid_temporal_order(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        sign_workflow_run_attestation(
            claims=_claims(**overrides),
            signer=Ed25519WorkflowRunAttestationSigner(
                private_key=Ed25519PrivateKey.generate(), key_id="key-1", rotation_epoch=1
            ),
        )


@pytest.mark.parametrize(
    "signature",
    [
        WorkflowRunSignature("HS256", "key-1", 1, b"signature"),
        WorkflowRunSignature("EdDSA", "", 1, b"signature"),
        WorkflowRunSignature("EdDSA", "key-1", 0, b"signature"),
        WorkflowRunSignature("EdDSA", "key-1", 1, b""),
    ],
)
def test_signing_rejects_invalid_signer_metadata(signature: WorkflowRunSignature) -> None:
    class Signer:
        def sign(self, payload: bytes) -> WorkflowRunSignature:
            return signature

    with pytest.raises(ValueError):
        sign_workflow_run_attestation(claims=_claims(), signer=Signer())
