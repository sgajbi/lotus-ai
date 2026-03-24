from __future__ import annotations

from dataclasses import dataclass
from threading import local

from app.config import settings
from app.contracts.deployment_split import DeploymentSplitStage
from app.contracts.evals import EvaluationApprovalGateSummaryDescriptor
from app.contracts.production_baseline import ProductionBaselineGovernanceStatusResponse
from app.contracts.retrieval import RetrievalGovernanceStatusResponse

_POSTURE_RESOLUTION_STATE = local()


def _build_production_baseline_governance_status(
    app_state: object | None,
) -> ProductionBaselineGovernanceStatusResponse:
    from app.services.production_baseline_governance import (
        build_production_baseline_governance_status,
    )

    return build_production_baseline_governance_status(app_state)


def _build_retrieval_governance_status(
    app_state: object | None,
) -> RetrievalGovernanceStatusResponse:
    from app.services.retrieval_governance_status import build_retrieval_governance_status

    return build_retrieval_governance_status()


@dataclass(frozen=True)
class DeploymentSplitPosture:
    configured_stage: DeploymentSplitStage
    effective_stage: DeploymentSplitStage
    blocking_findings: list[str]
    retrieval_degraded_findings: list[str]
    eval_degraded_findings: list[str]


def _resolve_reentrant_split_posture(
    configured_stage: DeploymentSplitStage,
) -> DeploymentSplitPosture:
    return DeploymentSplitPosture(
        configured_stage=configured_stage,
        effective_stage=configured_stage,
        blocking_findings=[],
        retrieval_degraded_findings=[],
        eval_degraded_findings=[],
    )


def _build_eval_split_approval_gates() -> list[EvaluationApprovalGateSummaryDescriptor]:
    from app.services.eval_approval_gate_summary import (
        build_first_use_case_approval_gate_summary,
        build_prompt_approval_gate_summary,
        build_provider_approval_gate_summary,
        build_retrieval_approval_gate_summary,
        build_safety_approval_gate_summary,
    )

    return [
        build_first_use_case_approval_gate_summary(),
        build_prompt_approval_gate_summary(),
        build_retrieval_approval_gate_summary(),
        build_provider_approval_gate_summary(),
        build_safety_approval_gate_summary(),
    ]


def resolve_configured_deployment_split_stage() -> DeploymentSplitStage:
    configured = settings.deployment_split_stage.strip().lower()
    mapping = {
        "unified": DeploymentSplitStage.UNIFIED,
        "split_ready": DeploymentSplitStage.SPLIT_READY,
        "retrieval_split_active": DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        "retrieval_and_evals_split_active": DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
    }
    return mapping.get(configured, DeploymentSplitStage.UNIFIED)


def resolve_deployment_split_posture(
    app_state: object | None = None,
) -> DeploymentSplitPosture:
    configured_stage = resolve_configured_deployment_split_stage()
    if configured_stage is DeploymentSplitStage.UNIFIED:
        return DeploymentSplitPosture(
            configured_stage=configured_stage,
            effective_stage=DeploymentSplitStage.UNIFIED,
            blocking_findings=[],
            retrieval_degraded_findings=[],
            eval_degraded_findings=[],
        )

    if getattr(_POSTURE_RESOLUTION_STATE, "active", False):
        return _resolve_reentrant_split_posture(configured_stage)

    _POSTURE_RESOLUTION_STATE.active = True
    try:
        production_baseline_governance = _build_production_baseline_governance_status(app_state)
        if not production_baseline_governance.governance_ready:
            return DeploymentSplitPosture(
                configured_stage=configured_stage,
                effective_stage=DeploymentSplitStage.UNIFIED,
                blocking_findings=[
                    "RFC-0020 production-baseline governance is not yet ready, so the platform cannot be treated as split-ready.",
                    *production_baseline_governance.governance_summary,
                ],
                retrieval_degraded_findings=[],
                eval_degraded_findings=[],
            )

        if configured_stage is DeploymentSplitStage.SPLIT_READY:
            return DeploymentSplitPosture(
                configured_stage=configured_stage,
                effective_stage=DeploymentSplitStage.SPLIT_READY,
                blocking_findings=[],
                retrieval_degraded_findings=[],
                eval_degraded_findings=[],
            )

        retrieval_governance = _build_retrieval_governance_status(app_state)
        retrieval_degraded_findings = (
            []
            if retrieval_governance.governance_ready
            else [
                "Retrieval split activation remains configured, but retrieval governance is degraded and operators should consider rolling back to the unified stage.",
                *retrieval_governance.governance_summary,
            ]
        )
        if configured_stage is DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE:
            return DeploymentSplitPosture(
                configured_stage=configured_stage,
                effective_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
                blocking_findings=[],
                retrieval_degraded_findings=retrieval_degraded_findings,
                eval_degraded_findings=[],
            )

        approval_gates = _build_eval_split_approval_gates()
        eval_degraded_findings = [
            "Eval split activation remains configured, but runtime-backed approval evidence is degraded across one or more governed rollout domains and operators should consider rolling back to the unified stage."
        ]
        eval_degraded_findings.extend(
            f"{gate.domain_label} approval gate is currently '{gate.evidence_state.value}'."
            for gate in approval_gates
            if not gate.approval_ready
        )
        if len(eval_degraded_findings) == 1:
            eval_degraded_findings = []

        return DeploymentSplitPosture(
            configured_stage=configured_stage,
            effective_stage=DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
            blocking_findings=[],
            retrieval_degraded_findings=retrieval_degraded_findings,
            eval_degraded_findings=eval_degraded_findings,
        )
    finally:
        _POSTURE_RESOLUTION_STATE.active = False


def resolve_effective_deployment_split_stage(
    app_state: object | None = None,
) -> tuple[DeploymentSplitStage, list[str]]:
    posture = resolve_deployment_split_posture(app_state)
    return posture.effective_stage, posture.blocking_findings
