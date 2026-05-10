from __future__ import annotations

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselineActivationReadinessResponse,
    ProductionBaselineGovernanceStatusResponse,
    ProductionBaselineRuntimeStatusResponse,
)
from app.contracts.providers import ProviderGovernanceStatusResponse
from app.contracts.use_cases import FirstUseCaseGovernanceStatusResponse
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.governance_readiness import summarize_governance_flags
from app.services.production_baseline_activation_readiness import (
    build_production_baseline_activation_readiness,
)
from app.services.provider_governance_status import build_provider_governance_status
from app.services.production_baseline_runbook_readiness import (
    build_production_baseline_runbook_readiness,
)
from app.services.production_baseline_runtime import build_production_baseline_runtime_status


def build_production_baseline_governance_status(
    app_state: object | None = None,
    *,
    runtime_status: ProductionBaselineRuntimeStatusResponse | None = None,
    activation_readiness: ProductionBaselineActivationReadinessResponse | None = None,
    provider_governance: ProviderGovernanceStatusResponse | None = None,
    first_use_case_governance: FirstUseCaseGovernanceStatusResponse | None = None,
) -> ProductionBaselineGovernanceStatusResponse:
    runtime_status = (
        runtime_status
        if runtime_status is not None
        else build_production_baseline_runtime_status(app_state)
    )
    activation_readiness = (
        activation_readiness
        if activation_readiness is not None
        else build_production_baseline_activation_readiness(
            app_state, runtime_status=runtime_status
        )
    )
    runbook_readiness = build_production_baseline_runbook_readiness()
    provider_governance = (
        provider_governance
        if provider_governance is not None
        else build_provider_governance_status()
    )
    first_use_case_governance = (
        first_use_case_governance
        if first_use_case_governance is not None
        else build_first_use_case_governance_status()
    )
    dependent_rollout_findings: list[str] = []
    if settings.provider_mode == "openai" and not provider_governance.governance_ready:
        dependent_rollout_findings.append(
            "Live-provider execution is configured, but provider governance is still blocked; technical bring-up must not be mistaken for approved live rollout."
        )
    if not first_use_case_governance.governance_ready:
        dependent_rollout_findings.append(
            "The current first downstream use case is not yet governance-ready, so the accepted production baseline must not be confused with downstream rollout approval."
        )
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        not dependent_rollout_findings,
    )
    return ProductionBaselineGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        provider_governance_ready=provider_governance.governance_ready,
        first_use_case_governance_ready=first_use_case_governance.governance_ready,
        dependent_rollout_findings=dependent_rollout_findings,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            runtime_status.status_summary[0],
            (
                "Production activation readiness is satisfied because all required baseline dependencies are production-standard."
                if activation_readiness.activation_ready
                else "Production activation readiness remains blocked until all required baseline dependencies move from fallback or blocked to production-standard."
            ),
            (
                "Production runbook readiness is complete and operator guidance now separates local demo setup from accepted go-live posture."
                if runbook_readiness.runbook_ready
                else "Production runbook readiness remains incomplete for at least one required operational path."
            ),
            (
                "Dependent rollout governance is also ready, so production baseline posture is not being overstated relative to the live-provider and first-use-case surfaces."
                if not dependent_rollout_findings
                else "Dependent rollout governance remains blocked, so production-baseline posture must still be interpreted alongside provider and first-use-case governance views."
            ),
        ],
    )
