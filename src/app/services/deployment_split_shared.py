from __future__ import annotations

from dataclasses import dataclass
from threading import local

from app.config import settings
from app.contracts.deployment_split import DeploymentSplitStage
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
    degraded_findings: list[str]


def _resolve_reentrant_split_posture(
    configured_stage: DeploymentSplitStage,
) -> DeploymentSplitPosture:
    if configured_stage is DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE:
        return DeploymentSplitPosture(
            configured_stage=configured_stage,
            effective_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
            blocking_findings=[
                "Eval plane activation is not yet implemented in the current RFC-0015 slice, so the configured stage is capped at retrieval-split active."
            ],
            degraded_findings=[],
        )
    return DeploymentSplitPosture(
        configured_stage=configured_stage,
        effective_stage=configured_stage,
        blocking_findings=[],
        degraded_findings=[],
    )


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
            degraded_findings=[],
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
                degraded_findings=[],
            )

        if configured_stage is DeploymentSplitStage.SPLIT_READY:
            return DeploymentSplitPosture(
                configured_stage=configured_stage,
                effective_stage=DeploymentSplitStage.SPLIT_READY,
                blocking_findings=[],
                degraded_findings=[],
            )

        retrieval_governance = _build_retrieval_governance_status(app_state)
        if configured_stage is DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE:
            degraded_findings = (
                []
                if retrieval_governance.governance_ready
                else [
                    "Retrieval split activation remains configured, but retrieval governance is degraded and operators should consider rolling back to the unified stage.",
                    *retrieval_governance.governance_summary,
                ]
            )
            return DeploymentSplitPosture(
                configured_stage=configured_stage,
                effective_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
                blocking_findings=[],
                degraded_findings=degraded_findings,
            )

        degraded_findings = (
            []
            if retrieval_governance.governance_ready
            else [
                "Retrieval split activation remains configured, but retrieval governance is degraded and operators should consider rolling back to the unified stage.",
                *retrieval_governance.governance_summary,
            ]
        )
        return DeploymentSplitPosture(
            configured_stage=configured_stage,
            effective_stage=DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
            blocking_findings=[
                "Eval plane activation is not yet implemented in the current RFC-0015 slice, so the configured stage is capped at retrieval-split active."
            ],
            degraded_findings=degraded_findings,
        )
    finally:
        _POSTURE_RESOLUTION_STATE.active = False


def resolve_effective_deployment_split_stage(
    app_state: object | None = None,
) -> tuple[DeploymentSplitStage, list[str]]:
    posture = resolve_deployment_split_posture(app_state)
    return posture.effective_stage, posture.blocking_findings
