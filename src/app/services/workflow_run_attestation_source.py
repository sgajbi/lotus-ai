from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from app.contracts.tasks import TaskExecutionResponse
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.task_execution_models import TaskExecutionContext


@dataclass(frozen=True)
class WorkflowRunAttestationSource:
    evaluator_id: str
    evaluator_policy_version: str
    provider_id: str
    model_id: str
    model_version: str
    model_risk_status: str
    model_risk_approval_ref: str
    input_evidence_sha256: str
    output_content_sha256: str
    replay_nonce: str


EVALUATOR_POLICY_BY_PACK = {
    "idea_explanation.pack": ("idea-explanation-guardrails", "idea-explanation-policy.v1"),
}


def capture_workflow_run_attestation_source(
    *,
    run_id: str,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
    registration: WorkflowPackRegistrationDescriptor,
    model_risk_status: str,
    model_risk_approval_ref: str | None,
) -> WorkflowRunAttestationSource:
    evaluator_id, evaluator_policy_version = EVALUATOR_POLICY_BY_PACK.get(
        registration.pack_id,
        (f"{registration.pack_id}.governed-evaluator", registration.compatibility_contract_version),
    )
    input_digest = _sha256(
        {
            "task_id": response.task_id,
            "context": context.request.context.model_dump(mode="json"),
            "expected_output_label": (
                context.request.expected_output_label.value
                if context.request.expected_output_label is not None
                else None
            ),
        }
    )
    output_digest = _sha256(
        {
            "status": response.status.value,
            "output_label": response.output_label.value,
            "message": response.result.message,
            "structured_output": response.result.structured_output,
        }
    )
    provider_id = response.audit.provider_id
    model_id = response.audit.model_id or "deterministic-stub"
    model_version = response.audit.model_version or (
        "stub.v1" if response.audit.stubbed else "model-version-unavailable"
    )
    replay_nonce = hashlib.sha256(
        f"{run_id}\x1f{context.request_id}\x1f{input_digest}\x1f{output_digest}".encode("utf-8")
    ).hexdigest()
    return WorkflowRunAttestationSource(
        evaluator_id=evaluator_id,
        evaluator_policy_version=evaluator_policy_version,
        provider_id=provider_id,
        model_id=model_id,
        model_version=model_version,
        model_risk_status=model_risk_status,
        model_risk_approval_ref=model_risk_approval_ref or "unverifiable",
        input_evidence_sha256=input_digest,
        output_content_sha256=output_digest,
        replay_nonce=replay_nonce,
    )


def _sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()
