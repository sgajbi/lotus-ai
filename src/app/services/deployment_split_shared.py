from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import DeploymentSplitStage
from app.contracts.production_baseline import ProductionBaselineGovernanceStatusResponse


def _build_production_baseline_governance_status(
    app_state: object | None,
) -> ProductionBaselineGovernanceStatusResponse:
    from app.services.production_baseline_governance import (
        build_production_baseline_governance_status,
    )

    return build_production_baseline_governance_status(app_state)


def resolve_configured_deployment_split_stage() -> DeploymentSplitStage:
    configured = settings.deployment_split_stage.strip().lower()
    mapping = {
        "unified": DeploymentSplitStage.UNIFIED,
        "split_ready": DeploymentSplitStage.SPLIT_READY,
        "retrieval_split_active": DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        "retrieval_and_evals_split_active": DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
    }
    return mapping.get(configured, DeploymentSplitStage.UNIFIED)


def resolve_effective_deployment_split_stage(
    app_state: object | None = None,
) -> tuple[DeploymentSplitStage, list[str]]:
    configured_stage = resolve_configured_deployment_split_stage()
    if configured_stage is DeploymentSplitStage.UNIFIED:
        return DeploymentSplitStage.UNIFIED, []
    if configured_stage is DeploymentSplitStage.SPLIT_READY:
        production_baseline_governance = _build_production_baseline_governance_status(app_state)
        if production_baseline_governance.governance_ready:
            return DeploymentSplitStage.SPLIT_READY, []
        return DeploymentSplitStage.UNIFIED, [
            "RFC-0020 production-baseline governance is not yet ready, so the platform cannot be treated as split-ready.",
            *production_baseline_governance.governance_summary,
        ]
    return DeploymentSplitStage.UNIFIED, [
        "Retrieval and eval plane activation are not yet implemented in the current RFC-0015 slice."
    ]
