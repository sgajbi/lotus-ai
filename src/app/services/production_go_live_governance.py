from __future__ import annotations

from app.config import settings
from app.contracts.production_go_live import ProductionGoLiveGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.production_go_live_activation_readiness import (
    build_production_go_live_activation_readiness,
)
from app.services.production_go_live_runbook_readiness import (
    build_production_go_live_runbook_readiness,
)
from app.services.production_go_live_use_case_approval import (
    build_production_go_live_use_case_approval,
)
from app.services.production_go_live_runtime import build_production_go_live_runtime_status
from app.services.provider_governance_status import build_provider_governance_status


def build_production_go_live_governance_status(
    app_state: object | None = None,
    *,
    runtime_status: object | None = None,
    activation_readiness: object | None = None,
    use_case_approval: object | None = None,
    provider_governance: object | None = None,
) -> ProductionGoLiveGovernanceStatusResponse:
    runtime_status = (
        runtime_status
        if runtime_status is not None
        else build_production_go_live_runtime_status(app_state)
    )
    provider_governance = (
        provider_governance
        if provider_governance is not None
        else build_provider_governance_status()
    )
    activation_readiness = (
        activation_readiness
        if activation_readiness is not None
        else build_production_go_live_activation_readiness(
            app_state,
            runtime_status=runtime_status,
            provider_governance=provider_governance,
        )
    )
    runbook_readiness = build_production_go_live_runbook_readiness()
    use_case_approval = (
        use_case_approval
        if use_case_approval is not None
        else build_production_go_live_use_case_approval(
            app_state,
            provider_governance=provider_governance,
            runtime_status=runtime_status,
        )
    )
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        provider_governance.governance_ready,
        use_case_approval.active_production_ready,
    )
    go_live_decision = _resolve_go_live_decision(
        activation_ready=activation_readiness.activation_ready,
        use_case_active_production_ready=use_case_approval.active_production_ready,
        use_case_limited_rollout_ready=use_case_approval.limited_rollout_ready,
    )
    return ProductionGoLiveGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        use_case_approval=use_case_approval,
        provider_governance_ready=provider_governance.governance_ready,
        go_live_decision=go_live_decision,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            runtime_status.status_summary[0],
            (
                "Production go-live activation is currently ready because platform approval, provider governance, and active live-provider posture are all aligned."
                if activation_readiness.activation_ready
                else "Production go-live activation remains blocked until platform approval, provider governance, and provider freeze or rollback posture all converge."
            ),
            (
                "Production go-live runbook readiness is complete and freeze or rollback guidance is now explicit."
                if runbook_readiness.runbook_ready
                else "Production go-live runbook readiness remains incomplete until provider incident and escalation procedures are fully approved."
            ),
            (
                "The named downstream use case is approved for active production traffic."
                if use_case_approval.active_production_ready
                else "The named downstream use case remains below active-production approval even when limited rollout is ready."
            ),
            f"Current go-live decision: {go_live_decision}.",
        ],
    )


def _resolve_go_live_decision(
    *,
    activation_ready: bool,
    use_case_active_production_ready: bool,
    use_case_limited_rollout_ready: bool,
) -> str:
    if activation_ready and use_case_active_production_ready:
        return "PRODUCTION_APPROVED"
    if use_case_limited_rollout_ready:
        return "LIMITED_ROLLOUT_ONLY"
    return "BLOCKED"
