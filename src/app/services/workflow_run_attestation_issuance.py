from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NoReturn

from app.contracts.workflow_run_attestation import (
    WorkflowRunAttestationClaims,
    WorkflowRunAttestationEnvelope,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRepository
from app.services.workflow_pack_run_supportability import (
    resolve_workflow_pack_run_record_supportability_status,
)
from app.services.workflow_run_attestation_signing import (
    WorkflowRunAttestationSigner,
    sign_workflow_run_attestation,
)


class WorkflowRunAttestationRunNotFoundError(LookupError):
    pass


class WorkflowRunAttestationNotIssuableError(ValueError):
    def __init__(self, *, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


def issue_workflow_run_attestation(
    *,
    run_id: str,
    run_repository: WorkflowPackRunRepository,
    signer: WorkflowRunAttestationSigner,
    issued_at_utc: datetime | None = None,
    ttl_seconds: int = 300,
) -> WorkflowRunAttestationEnvelope:
    run = run_repository.get_run(run_id=run_id)
    if run is None:
        raise WorkflowRunAttestationRunNotFoundError(
            f"Unknown workflow-pack run for attestation: {run_id}"
        )
    if ttl_seconds < 1 or ttl_seconds > 3600:
        raise ValueError("workflow-run attestation TTL must be between 1 and 3600 seconds")
    execution_completed_at = run.completed_at
    if execution_completed_at is None or run.runtime_state != "COMPLETED":
        _reject("execution_not_completed", "Workflow-pack execution is not completed.")
    supportability = resolve_workflow_pack_run_record_supportability_status(run)
    if supportability.value != "READY":
        _reject(
            "supportability_not_ready",
            f"Workflow-pack run supportability is `{supportability.value}`.",
        )
    if run.model_risk_status != "approved" or run.model_risk_approval_ref == "unverifiable":
        _reject(
            "model_risk_not_approved",
            "Workflow-pack run does not carry a verifiable approved model-risk decision.",
        )
    if run.stubbed:
        _reject(
            "stub_execution", "Stub workflow-pack output cannot receive an approved attestation."
        )
    issued_at = issued_at_utc or datetime.now(UTC)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ValueError("workflow-run attestation issue time must be timezone-aware")
    claims = WorkflowRunAttestationClaims(
        schema_version="lotus-ai.workflow-run-attestation.v1",
        issuer="lotus-ai",
        audience=run.caller_app,
        run_id=run.run_id,
        consumer_request_id=run.request_id,
        replay_nonce=run.replay_nonce,
        workflow_pack_id=run.pack_id,
        workflow_pack_version=run.pack_version,
        registration_ref=run.registration_ref,
        evaluator_id=run.evaluator_id,
        evaluator_policy_version=run.evaluator_policy_version,
        provider_id=run.provider_id,
        provider_mode=run.provider_mode,
        model_id=run.model_id,
        model_version=run.model_version,
        model_risk_status="approved",
        model_risk_approval_ref=run.model_risk_approval_ref,
        input_evidence_sha256=run.input_evidence_sha256,
        output_content_sha256=run.output_content_sha256,
        issued_at_utc=_timestamp(issued_at),
        execution_started_at_utc=run.execution_started_at,
        execution_completed_at_utc=execution_completed_at,
        expires_at_utc=_timestamp(issued_at + timedelta(seconds=ttl_seconds)),
        stubbed=False,
        supportability_status="READY",
    )
    return sign_workflow_run_attestation(claims=claims, signer=signer)


def _reject(reason_code: str, detail: str) -> NoReturn:
    raise WorkflowRunAttestationNotIssuableError(reason_code=reason_code, detail=detail)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
