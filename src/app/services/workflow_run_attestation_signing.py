from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Protocol

from app.contracts.workflow_run_attestation import (
    WorkflowRunAttestationClaims,
    WorkflowRunAttestationEnvelope,
    WorkflowRunAttestationSignature,
)


@dataclass(frozen=True)
class WorkflowRunSignature:
    algorithm: str
    key_id: str
    rotation_epoch: int
    signature: bytes


class WorkflowRunAttestationSigner(Protocol):
    def sign(self, payload: bytes) -> WorkflowRunSignature: ...


def canonical_attestation_payload(claims: WorkflowRunAttestationClaims) -> bytes:
    return json.dumps(
        claims.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def sign_workflow_run_attestation(
    *, claims: WorkflowRunAttestationClaims, signer: WorkflowRunAttestationSigner
) -> WorkflowRunAttestationEnvelope:
    _validate_temporal_order(claims)
    signed = signer.sign(canonical_attestation_payload(claims))
    if signed.algorithm != "EdDSA":
        raise ValueError("workflow-run attestation signer must use EdDSA")
    if not signed.key_id.strip() or signed.rotation_epoch < 1 or not signed.signature:
        raise ValueError("workflow-run attestation signer returned invalid key metadata")
    return WorkflowRunAttestationEnvelope(
        claims=claims,
        signature=WorkflowRunAttestationSignature(
            algorithm=signed.algorithm,
            key_id=signed.key_id,
            rotation_epoch=signed.rotation_epoch,
            signature_base64url=base64.urlsafe_b64encode(signed.signature)
            .rstrip(b"=")
            .decode("ascii"),
        ),
        key_discovery_path="/.well-known/lotus-ai-workflow-attestation-keys",
    )


def _validate_temporal_order(claims: WorkflowRunAttestationClaims) -> None:
    timestamps: dict[str, datetime] = {}
    for name in (
        "issued_at_utc",
        "execution_started_at_utc",
        "execution_completed_at_utc",
        "expires_at_utc",
    ):
        value = getattr(claims, name)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        timestamps[name] = parsed
    if timestamps["execution_completed_at_utc"] < timestamps["execution_started_at_utc"]:
        raise ValueError("execution completion must not precede execution start")
    if timestamps["issued_at_utc"] < timestamps["execution_completed_at_utc"]:
        raise ValueError("attestation issue time must not precede execution completion")
    if timestamps["expires_at_utc"] <= timestamps["issued_at_utc"]:
        raise ValueError("attestation expiry must follow issue time")
