from __future__ import annotations

from app.config import settings
from app.contracts.evals import EvaluationApprovalEvidenceState
from app.contracts.prompts import (
    PromptEvidenceReadinessItem,
    PromptEvidenceReadinessResponse,
)
from app.services.eval_approval_gate_summary import build_prompt_approval_gate_summary
from app.services.eval_catalog import build_evaluation_catalog
from app.services.governance_readiness import summarize_activation_items


def build_prompt_evidence_readiness() -> PromptEvidenceReadinessResponse:
    catalog = build_evaluation_catalog()
    staged_fixture_ids = {fixture.fixture_id for fixture in catalog.fixture_families}
    approval_gate = build_prompt_approval_gate_summary()
    prompt_fixture_pack_ready = {
        "prompt_promotion_examples",
        "prompt_rollback_examples",
    }.issubset(staged_fixture_ids)
    items = [
        PromptEvidenceReadinessItem(
            evidence_id="prompt_fixture_coverage_pack",
            status="READY" if prompt_fixture_pack_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Prompt promotion and rollback fixture families are staged for runtime-backed execution."
                if prompt_fixture_pack_ready
                else (
                    "Prompt-specific rollout fixture families are not yet staged in the governed "
                    "evaluation manifest."
                )
            ),
        ),
        PromptEvidenceReadinessItem(
            evidence_id="prompt_regression_run_baseline",
            status=_approval_gate_status(approval_gate.evidence_state),
            required_for_activation=True,
            notes=(
                "Runtime-backed prompt promotion and rollback evaluation runs currently satisfy the governed prompt approval gate."
                if approval_gate.approval_ready
                else approval_gate.notes[0]
            ),
        ),
        PromptEvidenceReadinessItem(
            evidence_id="prompt_audit_traceability_pack",
            status="READY",
            required_for_activation=True,
            notes=(
                "Task responses, audit records, and execution evidence now preserve prompt selection lineage plus latest control-event history."
            ),
        ),
        PromptEvidenceReadinessItem(
            evidence_id="prompt_rollback_evidence_pack",
            status="READY" if approval_gate.approval_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Runtime-backed rollback fixtures now prove restoration of prior prompt selection behavior."
                if approval_gate.approval_ready
                else (
                    "Rollback-proof evidence for reverting prompt changes and validating restored "
                    "runtime behavior is not yet recorded."
                )
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    evidence_ready = completed_required_item_count == required_item_count
    return PromptEvidenceReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        evidence_ready=evidence_ready,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
        approval_gate=approval_gate,
    )


def _approval_gate_status(evidence_state: EvaluationApprovalEvidenceState) -> str:
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_PASS:
        return "READY"
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS:
        return "IN_PROGRESS"
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_PARTIAL:
        return "PARTIAL"
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_FAIL:
        return "FAILED"
    if evidence_state == EvaluationApprovalEvidenceState.RUNTIME_STALE:
        return "STALE"
    if evidence_state == EvaluationApprovalEvidenceState.STAGED_ONLY:
        return "FOUNDATION_STAGED"
    return "NOT_READY"
