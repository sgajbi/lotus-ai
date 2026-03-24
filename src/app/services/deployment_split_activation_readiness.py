from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import (
    DeploymentSplitActivationReadinessResponse,
    DeploymentSplitStage,
)
from app.services.deployment_split_runtime import build_deployment_split_runtime_status


def build_deployment_split_activation_readiness(
    app_state: object | None = None,
) -> DeploymentSplitActivationReadinessResponse:
    runtime_status = build_deployment_split_runtime_status(app_state)
    split_active = runtime_status.effective_stage in {
        DeploymentSplitStage.RETRIEVAL_SPLIT_ACTIVE,
        DeploymentSplitStage.RETRIEVAL_AND_EVALS_SPLIT_ACTIVE,
    }
    blocking_findings = [
        *runtime_status.blocking_findings,
        *runtime_status.degraded_findings,
    ]
    activation_ready = (
        runtime_status.configured_stage is runtime_status.effective_stage
        and not runtime_status.degraded
    )
    return DeploymentSplitActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        configured_stage=runtime_status.configured_stage,
        effective_stage=runtime_status.effective_stage,
        split_ready=runtime_status.split_ready,
        split_active=split_active,
        activation_ready=activation_ready,
        degraded=runtime_status.degraded,
        blocking_findings=blocking_findings,
        activation_path=[
            "Keep RFC-0020 production-baseline governance ready before treating any configured split stage as activatable.",
            "Confirm /platform/deployment-split/runtime-status reports the configured stage as the effective stage before treating the split posture as active.",
            "Use /platform/observability/runtime-status and the retrieval and eval execution-status views to confirm active split planes are not degraded before rollout review.",
            "Treat rollback to UNIFIED as the first supported rollback target whenever retrieval or eval split posture remains blocked or degraded.",
        ],
    )
