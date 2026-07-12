from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from app.contracts.workflow_run_attestation import WorkflowRunAttestationSignature
from app.provider_retention_confirmations.contracts import (
    ProviderRetentionConfirmationClaims,
    ProviderRetentionConfirmationEnvelope,
    ProviderRetentionConfirmationRequest,
    ProviderRetentionOutcome,
)
from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationConflictError,
    ProviderRetentionConfirmationRecord,
    ProviderRetentionConfirmationRepository,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRepository
from app.services.workflow_run_attestation_signing import WorkflowRunAttestationSigner


class ProviderRetentionConfirmationNotFoundError(LookupError):
    pass


class ProviderRetentionConfirmationNotIssuableError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        super().__init__(message)


def issue_provider_retention_confirmation(
    *,
    run_id: str,
    request: ProviderRetentionConfirmationRequest,
    idempotency_key: str,
    caller_app: str,
    tenant_id: str,
    run_repository: WorkflowPackRunRepository,
    confirmation_repository: ProviderRetentionConfirmationRepository,
    signer: WorkflowRunAttestationSigner,
    issued_at_utc: datetime | None = None,
    ttl_seconds: int = 300,
) -> ProviderRetentionConfirmationEnvelope:
    fingerprint = _fingerprint(run_id, request, caller_app, tenant_id)
    run = run_repository.get_run(run_id=run_id)
    if run is None:
        raise ProviderRetentionConfirmationNotFoundError(run_id)
    if run.pack_id != "idea_explanation.pack" or run.caller_app != "lotus-idea":
        _reject("run_not_idea_owned", "Run is not an Idea explanation workflow run.")
    if caller_app != "lotus-ai-provider-operations":
        _reject("caller_not_authorized", "Only AI provider operations may record outcomes.")
    if run.tenant_id is None or tenant_id != run.tenant_id:
        _reject("tenant_mismatch", "Caller tenant does not match the workflow run.")
    if run.runtime_state != "COMPLETED" or run.completed_at is None:
        _reject("run_not_completed", "Workflow run is not completed.")
    if run.stubbed or run.provider_mode in {"disabled", "stub"}:
        _reject("provider_execution_not_live", "Stubbed provider execution cannot be confirmed.")
    if run.provider_id == "unverifiable" or run.model_id == "unverifiable":
        _reject("provider_identity_unverifiable", "Provider identity is not verifiable.")
    existing = confirmation_repository.get_by_idempotency_key(idempotency_key=idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProviderRetentionConfirmationConflictError(
                "idempotency key was reused with different provider confirmation input"
            )
        return existing.envelope
    replayed_provider_ref = confirmation_repository.get_by_provider_confirmation_ref(
        provider_confirmation_ref=request.provider_confirmation_ref
    )
    if replayed_provider_ref is not None:
        raise ProviderRetentionConfirmationConflictError(
            "provider confirmation reference was already recorded"
        )
    if ttl_seconds < 1 or ttl_seconds > 3600:
        raise ValueError("provider retention confirmation TTL must be between 1 and 3600 seconds")
    provider_decision_at = _parse_timestamp(
        request.provider_decision_at_utc,
        "provider_decision_at_utc",
    )
    issued_at = issued_at_utc or datetime.now(UTC)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ValueError("confirmation issue time must be timezone-aware")
    if provider_decision_at > issued_at:
        _reject("provider_decision_in_future", "Provider decision time cannot be in the future.")

    confirmation_id = (
        "provider_retention_"
        + hashlib.sha256(f"{idempotency_key}:{fingerprint}".encode("utf-8")).hexdigest()[:24]
    )
    claims = ProviderRetentionConfirmationClaims(
        schema_version="lotus-ai.provider-retention-confirmation.v1",
        issuer="lotus-ai",
        audience="lotus-idea",
        recorded_by="lotus-ai-provider-operations",
        confirmation_id=confirmation_id,
        workflow_run_id=run.run_id,
        workflow_pack_id=run.pack_id,
        tenant_id=run.tenant_id,
        provider_id=run.provider_id,
        provider_mode=run.provider_mode,
        model_id=run.model_id,
        model_version=run.model_version,
        provider_confirmation_ref=request.provider_confirmation_ref,
        retention_policy_id=request.retention_policy_id,
        outcome=request.outcome,
        provider_decision_at_utc=_timestamp(provider_decision_at),
        evidence_sha256=request.evidence_sha256,
        provider_failure_code=request.provider_failure_code,
        deletion_confirmed=request.outcome is ProviderRetentionOutcome.DELETION_CONFIRMED,
        raw_prompt_included=False,
        raw_output_included=False,
        client_identifier_included=False,
        supportability_status=(
            "BLOCKED" if request.outcome is ProviderRetentionOutcome.PROVIDER_FAILURE else "READY"
        ),
        issued_at_utc=_timestamp(issued_at),
        expires_at_utc=_timestamp(issued_at + timedelta(seconds=ttl_seconds)),
        replay_nonce=hashlib.sha256(
            f"{run.replay_nonce}:{request.provider_confirmation_ref}:{fingerprint}".encode()
        ).hexdigest(),
    )
    signed = signer.sign(canonical_confirmation_payload(claims))
    if signed.algorithm != "EdDSA" or not signed.signature:
        raise ValueError("provider retention confirmation signer returned invalid signature")
    envelope = ProviderRetentionConfirmationEnvelope(
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
    stored = confirmation_repository.save(
        ProviderRetentionConfirmationRecord(
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            envelope=envelope,
        )
    )
    return stored.envelope


def canonical_confirmation_payload(claims: ProviderRetentionConfirmationClaims) -> bytes:
    return json.dumps(
        claims.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _fingerprint(
    run_id: str,
    request: ProviderRetentionConfirmationRequest,
    caller_app: str,
    tenant_id: str,
) -> str:
    payload = {
        "run_id": run_id,
        "request": request.model_dump(mode="json"),
        "caller_app": caller_app,
        "tenant_id": tenant_id,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _reject(reason_code: str, message: str) -> NoReturn:
    raise ProviderRetentionConfirmationNotIssuableError(reason_code, message)
