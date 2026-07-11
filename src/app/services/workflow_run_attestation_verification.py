from __future__ import annotations

import base64
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.contracts.workflow_run_attestation import (
    WorkflowRunAttestationEnvelope,
    WorkflowRunAttestationKeyDiscoveryResponse,
    WorkflowRunAttestationPublicKey,
)
from app.services.workflow_run_attestation_signing import canonical_attestation_payload


def verify_workflow_run_attestation(
    *,
    envelope: WorkflowRunAttestationEnvelope,
    key_discovery: WorkflowRunAttestationKeyDiscoveryResponse,
    expected_audience: str,
    verified_at_utc: datetime,
) -> None:
    if verified_at_utc.tzinfo is None or verified_at_utc.utcoffset() is None:
        raise ValueError("verified_at_utc must be timezone-aware")
    if envelope.claims.issuer != key_discovery.issuer:
        raise ValueError("workflow-run attestation issuer is not trusted")
    if envelope.claims.audience != expected_audience:
        raise ValueError("workflow-run attestation audience does not match consumer")
    expires_at = _timestamp(envelope.claims.expires_at_utc, "expires_at_utc")
    issued_at = _timestamp(envelope.claims.issued_at_utc, "issued_at_utc")
    if verified_at_utc < issued_at or verified_at_utc >= expires_at:
        raise ValueError("workflow-run attestation is not currently valid")
    key = _resolve_key(key_discovery, envelope.signature.key_id)
    if key.status == "revoked":
        raise ValueError("workflow-run attestation key is revoked")
    if key.rotation_epoch != envelope.signature.rotation_epoch:
        raise ValueError("workflow-run attestation rotation epoch does not match key")
    key_not_before = _timestamp(key.not_before_utc, "key.not_before_utc")
    if issued_at < key_not_before:
        raise ValueError("workflow-run attestation predates signing key validity")
    if key.not_after_utc is not None and issued_at >= _timestamp(
        key.not_after_utc, "key.not_after_utc"
    ):
        raise ValueError("workflow-run attestation exceeds signing key validity")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_decode(key.public_key_base64url))
        public_key.verify(
            _decode(envelope.signature.signature_base64url),
            canonical_attestation_payload(envelope.claims),
        )
    except (ValueError, InvalidSignature) as exc:
        raise ValueError("workflow-run attestation signature verification failed") from exc


def _resolve_key(
    discovery: WorkflowRunAttestationKeyDiscoveryResponse, key_id: str
) -> WorkflowRunAttestationPublicKey:
    matches = [key for key in discovery.keys if key.key_id == key_id]
    if len(matches) != 1:
        raise ValueError("workflow-run attestation key id is unknown or ambiguous")
    return matches[0]


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError as exc:
        raise ValueError("workflow-run attestation contains invalid base64url") from exc


def _timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed
