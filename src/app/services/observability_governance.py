from __future__ import annotations

from app.config import settings
from app.contracts.deployment_split import DeploymentSplitRuntimeStatusResponse
from app.contracts.observability import (
    ObservabilityActivationReadinessResponse,
    ObservabilityGovernanceStatusResponse,
    ObservabilityRuntimeStatusResponse,
)
from app.services.governance_readiness import summarize_governance_flags
from app.services.deployment_split_runtime import build_deployment_split_runtime_status
from app.services.observability_activation_readiness import build_observability_activation_readiness
from app.services.readiness_catalog import build_observability_runbook_readiness
from app.services.observability_runtime import build_observability_runtime_status


def build_observability_governance_status(
    *,
    deployment_split: DeploymentSplitRuntimeStatusResponse | None = None,
    runtime_status: ObservabilityRuntimeStatusResponse | None = None,
    activation_readiness: ObservabilityActivationReadinessResponse | None = None,
) -> ObservabilityGovernanceStatusResponse:
    deployment_split = (
        deployment_split
        if deployment_split is not None
        else build_deployment_split_runtime_status()
    )
    runtime_status = (
        runtime_status
        if runtime_status is not None
        else build_observability_runtime_status(deployment_split=deployment_split)
    )
    activation_readiness = (
        activation_readiness
        if activation_readiness is not None
        else build_observability_activation_readiness(runtime_status=runtime_status)
    )
    runbook_readiness = build_observability_runbook_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
    )
    return ObservabilityGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            "Observability now exposes bounded runtime, incident-summary, and caller, tenant, and capability breakdown surfaces through one in-service API family.",
            (
                "Activation readiness is satisfied because all governed domains expose incident evidence and the supporting audit and caller-policy stores are SQL-backed."
                if activation_readiness.activation_ready
                else "Activation readiness remains blocked; inspect bounded findings for store, domain, incident-evidence, and AI no-sensitive telemetry posture before rollout."
            ),
            (
                "Runbook readiness is complete for runtime review, incident review, and authorization-aware breakdown inspection."
                if runbook_readiness.runbook_ready
                else "Runbook readiness is incomplete for at least one required observability operator path."
            ),
            (
                "Observability summaries remain aligned with the current deployment-split stage and can be used to review unified versus active split-plane posture coherently."
                if not deployment_split.degraded
                else "Observability summaries remain aligned with the current deployment-split stage, but split-plane degradation still requires rollback-aware incident review."
            ),
        ],
    )
