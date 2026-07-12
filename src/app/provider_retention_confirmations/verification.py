from __future__ import annotations

import base64
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.contracts.workflow_run_attestation import WorkflowRunAttestationKeyDiscoveryResponse
from app.provider_retention_confirmations.contracts import (
    ProviderRetentionConfirmationEnvelope,
)
from app.provider_retention_confirmations.service import canonical_confirmation_payload


def verify_provider_retention_confirmation(
    envelope: ProviderRetentionConfirmationEnvelope,
    *,
    key_discovery: WorkflowRunAttestationKeyDiscoveryResponse,
    expected_tenant_id: str,
    at_utc: datetime | None = None,
) -> None:
    now = at_utc or datetime.now(UTC)
    issued = _timestamp(envelope.claims.issued_at_utc)
    expires = _timestamp(envelope.claims.expires_at_utc)
    if now < issued or now >= expires:
        raise ValueError("provider retention confirmation is not currently valid")
    if envelope.claims.tenant_id != expected_tenant_id:
        raise ValueError("provider retention confirmation tenant does not match")
    matching = [
        key
        for key in key_discovery.keys
        if key.key_id == envelope.signature.key_id
        and key.rotation_epoch == envelope.signature.rotation_epoch
    ]
    if len(matching) != 1:
        raise ValueError("provider retention confirmation key is unknown or ambiguous")
    key = matching[0]
    if key.status == "revoked":
        raise ValueError("provider retention confirmation key is revoked")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_decode(key.public_key_base64url))
        public_key.verify(
            _decode(envelope.signature.signature_base64url),
            canonical_confirmation_payload(envelope.claims),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("provider retention confirmation signature verification failed") from exc


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("provider retention confirmation timestamp must be timezone-aware")
    return parsed.astimezone(UTC)
