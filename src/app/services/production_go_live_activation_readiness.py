from __future__ import annotations

from app.config import settings
from app.contracts.production_go_live import (
    ProductionGoLiveActivationReadinessResponse,
    ProductionGoLiveFreezeState,
    ProductionGoLiveRollbackState,
)
from app.services.production_go_live_runtime import build_production_go_live_runtime_status
from app.services.provider_governance_status import build_provider_governance_status


def build_production_go_live_activation_readiness(
    app_state: object | None = None,
    *,
    runtime_status: object | None = None,
    provider_governance: object | None = None,
) -> ProductionGoLiveActivationReadinessResponse:
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
    activation_ready = (
        runtime_status.platform_production_approved
        and provider_governance.governance_ready
        and runtime_status.provider_freeze_state is ProductionGoLiveFreezeState.ACTIVE
    )
    blocking_findings = list(runtime_status.blocking_findings)
    if not provider_governance.governance_ready:
        blocking_findings.append(
            "Provider governance is not yet approved, so live-provider technical success must not be treated as production go-live activation."
        )
    if runtime_status.provider_freeze_state is ProductionGoLiveFreezeState.FROZEN:
        blocking_findings.append(
            "Live-provider traffic is currently frozen at the rollout layer and must remain below active production until review completes."
        )
    elif runtime_status.provider_freeze_state is ProductionGoLiveFreezeState.REVIEW_REQUIRED:
        blocking_findings.append(
            "Live-provider rollout remains active in configuration, but production go-live review requires either approval recovery or bounded freeze/rollback."
        )
    if runtime_status.provider_rollback_state is ProductionGoLiveRollbackState.RECOMMENDED:
        blocking_findings.append(
            "Rollback to the allowlisted-disabled provider rollout target is currently recommended before treating the live path as production-approved."
        )
    return ProductionGoLiveActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runtime_status=runtime_status,
        provider_governance_ready=provider_governance.governance_ready,
        activation_ready=activation_ready,
        blocking_findings=blocking_findings,
        activation_path=[
            "Confirm `/platform/production-go-live/runtime-status` reports both platform production approval and active provider freeze posture.",
            "Review `/platform/providers/governance-status` before treating live-provider traffic as production-approved.",
            "Use `provider_rollout_state=ALLOWLISTED_DISABLED` as the bounded freeze and rollback target whenever live-provider approval falls below production expectations.",
        ],
    )
