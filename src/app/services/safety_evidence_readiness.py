from __future__ import annotations

from app.config import settings
from app.services.runtime_readiness import get_audit_store_runtime_status
from app.contracts.evals import EvaluationApprovalEvidenceState
from app.contracts.safety import SafetyEvidenceReadinessItem, SafetyEvidenceReadinessResponse
from app.services.eval_approval_gate_summary import build_safety_approval_gate_summary
from app.services.eval_catalog import build_evaluation_catalog
from app.services.governance_readiness import summarize_activation_items


def build_safety_evidence_readiness() -> SafetyEvidenceReadinessResponse:
    catalog = build_evaluation_catalog()
    staged_fixture_ids = {fixture.fixture_id for fixture in catalog.fixture_families}
    approval_gate = build_safety_approval_gate_summary()
    policy_fixture_ready = "safety_policy_examples" in staged_fixture_ids
    runtime_fixture_ready = "safety_runtime_examples" in staged_fixture_ids
    # Measured, not asserted (issue #154): traceability depends on the audit
    # store actually being able to persist and serve the records.
    audit_traceability_ready = get_audit_store_runtime_status().status in {
        "READY",
        "DEGRADED",
    }
    runtime_evidence_status = _approval_gate_status(approval_gate.evidence_state)
    runtime_evidence_notes = {
        EvaluationApprovalEvidenceState.STAGED_ONLY: (
            "Safety runtime fixture families are staged, but no runtime-backed safety evaluation run exists yet."
        ),
        EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS: (
            "Runtime-backed safety evaluation is currently in progress."
        ),
        EvaluationApprovalEvidenceState.RUNTIME_PARTIAL: (
            "Runtime-backed safety evidence is only partially complete across the governed fixture families."
        ),
        EvaluationApprovalEvidenceState.RUNTIME_PASS: (
            "Runtime-backed safety evaluation covers both policy and execution fixture families with passing evidence."
        ),
        EvaluationApprovalEvidenceState.RUNTIME_FAIL: (
            "Runtime-backed safety evaluation recorded a failing result and currently blocks governed rollout."
        ),
        EvaluationApprovalEvidenceState.RUNTIME_STALE: (
            "Runtime-backed safety evaluation is stale against the current fixture manifest."
        ),
        EvaluationApprovalEvidenceState.NO_EVIDENCE: (
            "No runtime-backed safety evidence is currently recorded."
        ),
    }
    items = [
        SafetyEvidenceReadinessItem(
            evidence_id="safety_policy_fixture_pack",
            status="READY" if policy_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Safety policy fixture coverage is staged and can be executed through the runtime-backed evaluation path."
                if policy_fixture_ready
                else "Safety policy fixture coverage is not yet staged in the governed evaluation manifest."
            ),
        ),
        SafetyEvidenceReadinessItem(
            evidence_id="safety_runtime_fixture_pack",
            status="READY" if runtime_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Safety runtime fixtures cover pass-through, redaction, blocked, and degraded enforcement behavior."
                if runtime_fixture_ready
                else "Safety runtime fixture coverage is not yet staged in the governed evaluation manifest."
            ),
        ),
        SafetyEvidenceReadinessItem(
            evidence_id="safety_runtime_approval_baseline",
            status=runtime_evidence_status,
            required_for_activation=True,
            notes=runtime_evidence_notes[approval_gate.evidence_state],
        ),
        SafetyEvidenceReadinessItem(
            evidence_id="safety_audit_traceability_pack",
            status="READY" if audit_traceability_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Task responses, audit records, and execution evidence now preserve exact runtime safety outcomes including blocked, degraded, and redacted behavior."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    evidence_ready = completed_required_item_count == required_item_count
    return SafetyEvidenceReadinessResponse(
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
