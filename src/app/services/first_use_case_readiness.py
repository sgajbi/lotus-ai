from __future__ import annotations

from app.config import settings
from app.contracts.access_control import CallerLifecycleStatus
from app.contracts.evals import EvaluationApprovalEvidenceState
from app.contracts.tasks import OutputLabel
from app.contracts.use_cases import FirstUseCaseReadinessItem, FirstUseCaseReadinessResponse
from app.services.caller_policy_store import get_caller_policy_repository
from app.services.eval_approval_gate_summary import build_first_use_case_approval_gate_summary
from app.services.eval_catalog import build_evaluation_catalog
from app.services.governance_readiness import summarize_activation_items
from app.services.safety_runtime import build_safety_execution_outcome

_FIRST_USE_CASE_ID = "lotus_performance.analytics_commentary.v1"
_FIRST_USE_CASE_CALLER_APP = "lotus-performance"
_FIRST_USE_CASE_TASK_ID = "explain.v1"
_FIRST_USE_CASE_FIXTURE_ID = "lotus_performance_first_use_case_examples"


def build_first_use_case_readiness() -> FirstUseCaseReadinessResponse:
    catalog = build_evaluation_catalog()
    approval_gate = build_first_use_case_approval_gate_summary()
    staged_fixture_ids = {fixture.fixture_id for fixture in catalog.fixture_families}
    policy = get_caller_policy_repository().get_policy(_FIRST_USE_CASE_CALLER_APP)
    safety_outcome = build_safety_execution_outcome(OutputLabel.EXPLANATION_ONLY)

    caller_policy_ready = (
        policy is not None
        and policy.lifecycle_status == CallerLifecycleStatus.ACTIVE
        and _FIRST_USE_CASE_TASK_ID in policy.allowed_task_ids
        and policy.allow_live_provider is False
    )
    fixture_pack_ready = _FIRST_USE_CASE_FIXTURE_ID in staged_fixture_ids
    safety_ready = safety_outcome.output_label == OutputLabel.EXPLANATION_ONLY.value and (
        safety_outcome.redaction_posture.value == "MINIMIZATION_REQUIRED"
    )

    items = [
        FirstUseCaseReadinessItem(
            evidence_id="lotus_performance_caller_policy",
            status="READY" if caller_policy_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Caller policy explicitly recognizes lotus-performance for explain.v1, requires bounded tenant scope, and keeps live-provider execution disabled for this first use case."
                if caller_policy_ready
                else (
                    "Caller policy does not yet recognize lotus-performance with the bounded explain.v1-only posture required for the first use case."
                )
            ),
        ),
        FirstUseCaseReadinessItem(
            evidence_id="lotus_performance_eval_fixture_pack",
            status="READY" if fixture_pack_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "The lotus-performance first-use-case evaluation fixture family is staged in the governed evaluation manifest."
                if fixture_pack_ready
                else "The lotus-performance first-use-case evaluation fixture family is not yet staged."
            ),
        ),
        FirstUseCaseReadinessItem(
            evidence_id="lotus_performance_runtime_eval_evidence",
            status=_approval_gate_status(approval_gate.evidence_state),
            required_for_activation=True,
            notes=(
                "Runtime-backed lotus-performance first-use-case evaluation runs currently satisfy the governed approval gate."
                if approval_gate.approval_ready
                else approval_gate.notes[0]
            ),
        ),
        FirstUseCaseReadinessItem(
            evidence_id="lotus_performance_explanation_safety_posture",
            status="READY" if safety_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "EXPLANATION_ONLY outputs still run through the governed safety layer with minimization-required posture for the first use case."
                if safety_ready
                else "The first use case no longer resolves to the expected explanation-only minimization posture."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    readiness_ready = completed_required_item_count == required_item_count

    return FirstUseCaseReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        use_case_id=_FIRST_USE_CASE_ID,
        downstream_app=_FIRST_USE_CASE_CALLER_APP,
        readiness_ready=readiness_ready,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        approval_gate=approval_gate,
        items=items,
        status_summary=[
            (
                "Lotus-performance first-use-case readiness is currently backed by runtime-produced evaluation evidence, bounded caller identity, and explanation-only safety posture."
                if readiness_ready
                else (
                    "Lotus-performance first-use-case readiness is still blocked until runtime-produced evaluation evidence reaches the governed approval threshold."
                )
            ),
            "This readiness surface is limited to bounded onboarding evidence for lotus-performance analytics commentary; it does not imply broad downstream rollout by itself.",
        ],
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
