from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import (
    DeploymentSplitActivationReadinessResponse,
    DeploymentSplitGovernanceStatusResponse,
    DeploymentSplitRuntimeStatusResponse,
)
from app.contracts.observability import ObservabilityGovernanceStatusResponse
from app.services.deployment_split_activation_readiness import (
    build_deployment_split_activation_readiness,
)
from app.services.deployment_split_runbook_readiness import (
    build_deployment_split_runbook_readiness,
)
from app.services.deployment_split_runtime import build_deployment_split_runtime_status
from app.services.governance_readiness import summarize_governance_flags
from app.services.observability_governance import build_observability_governance_status


def build_deployment_split_governance_status(
    app_state: object | None = None,
    *,
    runtime_status: DeploymentSplitRuntimeStatusResponse | None = None,
    activation_readiness: DeploymentSplitActivationReadinessResponse | None = None,
    observability_governance: ObservabilityGovernanceStatusResponse | None = None,
) -> DeploymentSplitGovernanceStatusResponse:
    runtime_status = (
        runtime_status
        if runtime_status is not None
        else build_deployment_split_runtime_status(app_state)
    )
    activation_readiness = (
        activation_readiness
        if activation_readiness is not None
        else build_deployment_split_activation_readiness(app_state, runtime_status=runtime_status)
    )
    runbook_readiness = build_deployment_split_runbook_readiness()
    observability_governance = (
        observability_governance
        if observability_governance is not None
        else build_observability_governance_status()
    )
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        observability_governance.governance_ready,
    )
    return DeploymentSplitGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        observability_governance_ready=observability_governance.governance_ready,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            runtime_status.status_summary[0],
            (
                "Deployment-split activation readiness is satisfied because the configured stage is effective and no split-plane degradation remains active."
                if activation_readiness.activation_ready
                else "Deployment-split activation readiness remains blocked until the configured stage becomes effective without blocked or degraded split-plane posture."
            ),
            (
                "Deployment-split runbook readiness is complete for unified front-door ownership, cross-plane incident review, and rollback to UNIFIED."
                if runbook_readiness.runbook_ready
                else "Deployment-split runbook readiness remains incomplete for at least one required operator path."
            ),
            (
                "Cross-plane observability governance is ready, so split posture can be reviewed without conflicting runtime or incident-evidence truth."
                if observability_governance.governance_ready
                else "Cross-plane observability governance remains blocked, so split activation must not outrun the observability and incident-evidence surfaces."
            ),
        ],
    )
