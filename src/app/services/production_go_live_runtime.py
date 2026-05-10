from __future__ import annotations

from app.config import settings
from app.contracts.production_go_live import (
    ProductionGoLiveDomainDescriptor,
    ProductionGoLiveDomainStatus,
    ProductionGoLiveFreezeState,
    ProductionGoLivePlatformState,
    ProductionGoLiveRollbackState,
    ProductionGoLiveRuntimeStatusResponse,
    ProductionGoLiveUseCaseState,
)
from app.contracts.providers import ProviderExecutionMode, ProviderRolloutState
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status
from app.services.production_go_live_approval_domains import (
    build_managed_object_storage_approval_domain,
    build_managed_secret_approval_domain,
)
from app.services.provider_governance_status import build_provider_governance_status


def build_production_go_live_runtime_status(
    app_state: object | None = None,
    *,
    baseline: object | None = None,
    provider_governance: object | None = None,
    first_use_case_governance: object | None = None,
) -> ProductionGoLiveRuntimeStatusResponse:
    baseline = (
        baseline if baseline is not None else build_production_baseline_runtime_status(app_state)
    )
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
    managed_secret = build_managed_secret_approval_domain()
    managed_object_store = build_managed_object_storage_approval_domain()

    approval_domains = [
        managed_secret,
        managed_object_store,
        ProductionGoLiveDomainDescriptor(
            domain_id="live_provider_governance",
            status=_provider_domain_status(provider_governance.governance_ready),
            required_for_platform_approval=settings.provider_mode
            in {
                ProviderExecutionMode.OPENAI.value,
                ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
            },
            configured_mode=settings.provider_mode,
            review_surface="/platform/providers/governance-status",
            detail=(
                "Live-provider governance is currently ready for the configured provider posture."
                if provider_governance.governance_ready
                else "Live-provider execution may be technically enabled, but provider governance is not yet approved for production go-live."
            ),
        ),
        ProductionGoLiveDomainDescriptor(
            domain_id="downstream_use_case_production",
            status=_use_case_domain_status(
                use_case_production_approved=first_use_case_governance.active_production_ready,
                governance_ready=first_use_case_governance.governance_ready,
            ),
            required_for_platform_approval=False,
            configured_mode=first_use_case_governance.rollout_stage.value,
            review_surface="/platform/use-cases/first-production-use-case/governance-status",
            detail=(
                "The current first use case is approved for active production traffic."
                if first_use_case_governance.active_production_ready
                else "The current first use case remains below active production approval and should not be treated as fully approved live traffic."
            ),
        ),
    ]

    production_capable = baseline.posture in {
        baseline.posture.PROD_SHAPED_LOCAL,
        baseline.posture.PRODUCTION_READY,
    }
    platform_production_approved = (
        baseline.production_ready
        and managed_secret.status is ProductionGoLiveDomainStatus.APPROVED
        and managed_object_store.status is ProductionGoLiveDomainStatus.APPROVED
        and (
            settings.provider_mode
            not in {
                ProviderExecutionMode.OPENAI.value,
                ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
            }
            or provider_governance.governance_ready
        )
    )
    use_case_production_approved = first_use_case_governance.active_production_ready
    provider_freeze_state = _resolve_provider_freeze_state(
        provider_mode=settings.provider_mode,
        rollout_state=settings.provider_rollout_state,
        provider_governance_ready=provider_governance.governance_ready,
    )
    provider_rollback_state = _resolve_provider_rollback_state(
        provider_freeze_state=provider_freeze_state,
        rollout_state=settings.provider_rollout_state,
    )
    provider_rollback_target_state = _resolve_provider_rollback_target_state(
        provider_freeze_state=provider_freeze_state,
        provider_rollback_state=provider_rollback_state,
    )

    blocked_domain_count = sum(
        1
        for domain in approval_domains
        if domain.required_for_platform_approval
        and domain.status is not ProductionGoLiveDomainStatus.APPROVED
    )
    blocking_findings = [
        domain.detail
        for domain in approval_domains
        if domain.required_for_platform_approval
        and domain.status is not ProductionGoLiveDomainStatus.APPROVED
    ]

    return ProductionGoLiveRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        platform_state=_resolve_platform_state(
            production_capable=production_capable,
            platform_production_approved=platform_production_approved,
        ),
        use_case_state=_resolve_use_case_state(
            use_case_production_approved=use_case_production_approved,
            use_case_governance_ready=first_use_case_governance.governance_ready,
        ),
        technically_running=True,
        production_capable=production_capable,
        platform_production_approved=platform_production_approved,
        use_case_production_approved=use_case_production_approved,
        provider_freeze_state=provider_freeze_state,
        provider_rollback_state=provider_rollback_state,
        provider_rollback_target_state=provider_rollback_target_state,
        approval_domain_count=len(approval_domains),
        blocked_domain_count=blocked_domain_count,
        approval_domains=approval_domains,
        blocking_findings=blocking_findings,
        status_summary=[
            (
                "Lotus-ai is technically running but has not yet crossed into prod-shaped or production-ready baseline posture."
                if not production_capable
                else "Lotus-ai has crossed into production-capable baseline posture, but final go-live approval remains a separate production boundary."
            ),
            (
                "Platform production approval is currently satisfied."
                if platform_production_approved
                else "Platform production approval remains blocked pending managed infrastructure approval domains."
            ),
            (
                "Downstream use-case production approval remains separate from platform approval and is not yet active for the current first use case."
                if not use_case_production_approved
                else "The current named downstream use case is approved for active production traffic."
            ),
            _build_provider_control_summary(
                provider_freeze_state=provider_freeze_state,
                provider_rollback_state=provider_rollback_state,
                provider_rollback_target_state=provider_rollback_target_state,
            ),
        ],
    )


def _provider_domain_status(governance_ready: bool) -> ProductionGoLiveDomainStatus:
    return (
        ProductionGoLiveDomainStatus.APPROVED
        if governance_ready
        else ProductionGoLiveDomainStatus.INFORMATIONAL
    )


def _use_case_domain_status(
    *, use_case_production_approved: bool, governance_ready: bool
) -> ProductionGoLiveDomainStatus:
    if use_case_production_approved:
        return ProductionGoLiveDomainStatus.APPROVED
    if governance_ready:
        return ProductionGoLiveDomainStatus.INFORMATIONAL
    return ProductionGoLiveDomainStatus.BLOCKED


def _resolve_platform_state(
    *, production_capable: bool, platform_production_approved: bool
) -> ProductionGoLivePlatformState:
    if platform_production_approved:
        return ProductionGoLivePlatformState.PLATFORM_PRODUCTION_APPROVED
    if production_capable:
        return ProductionGoLivePlatformState.PRODUCTION_CAPABLE
    return ProductionGoLivePlatformState.TECHNICALLY_RUNNING


def _resolve_use_case_state(
    *, use_case_production_approved: bool, use_case_governance_ready: bool
) -> ProductionGoLiveUseCaseState:
    if use_case_production_approved:
        return ProductionGoLiveUseCaseState.USE_CASE_PRODUCTION_APPROVED
    if use_case_governance_ready:
        return ProductionGoLiveUseCaseState.LIMITED_ROLLOUT_ONLY
    return ProductionGoLiveUseCaseState.PRE_PROD_VALIDATION


def _resolve_provider_freeze_state(
    *, provider_mode: str, rollout_state: str, provider_governance_ready: bool
) -> ProductionGoLiveFreezeState:
    if provider_mode not in {
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }:
        return ProductionGoLiveFreezeState.NOT_APPLICABLE
    if rollout_state in {
        ProviderRolloutState.DOCUMENTED_ONLY.value,
        ProviderRolloutState.STUB_DEFAULT.value,
    }:
        return ProductionGoLiveFreezeState.NOT_APPLICABLE
    if rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED.value:
        return ProductionGoLiveFreezeState.FROZEN
    if (
        rollout_state
        in {
            ProviderRolloutState.CANARY_ENABLED.value,
            ProviderRolloutState.ROLLED_OUT.value,
        }
        and not provider_governance_ready
    ):
        return ProductionGoLiveFreezeState.REVIEW_REQUIRED
    return ProductionGoLiveFreezeState.ACTIVE


def _resolve_provider_rollback_state(
    *, provider_freeze_state: ProductionGoLiveFreezeState, rollout_state: str
) -> ProductionGoLiveRollbackState:
    if provider_freeze_state is ProductionGoLiveFreezeState.NOT_APPLICABLE:
        return ProductionGoLiveRollbackState.NOT_APPLICABLE
    if provider_freeze_state is ProductionGoLiveFreezeState.FROZEN:
        return ProductionGoLiveRollbackState.COMPLETED
    if provider_freeze_state is ProductionGoLiveFreezeState.REVIEW_REQUIRED:
        return ProductionGoLiveRollbackState.RECOMMENDED
    if rollout_state in {
        ProviderRolloutState.CANARY_ENABLED.value,
        ProviderRolloutState.ROLLED_OUT.value,
    }:
        return ProductionGoLiveRollbackState.AVAILABLE
    return ProductionGoLiveRollbackState.NOT_APPLICABLE


def _resolve_provider_rollback_target_state(
    *,
    provider_freeze_state: ProductionGoLiveFreezeState,
    provider_rollback_state: ProductionGoLiveRollbackState,
) -> str | None:
    if provider_rollback_state in {
        ProductionGoLiveRollbackState.AVAILABLE,
        ProductionGoLiveRollbackState.RECOMMENDED,
    }:
        return ProviderRolloutState.ALLOWLISTED_DISABLED.value
    if provider_freeze_state is ProductionGoLiveFreezeState.FROZEN:
        return ProviderRolloutState.ALLOWLISTED_DISABLED.value
    return None


def _build_provider_control_summary(
    *,
    provider_freeze_state: ProductionGoLiveFreezeState,
    provider_rollback_state: ProductionGoLiveRollbackState,
    provider_rollback_target_state: str | None,
) -> str:
    if provider_freeze_state is ProductionGoLiveFreezeState.NOT_APPLICABLE:
        return "No live-provider freeze posture applies because live-provider traffic is not currently in a governed active rollout state."
    if provider_freeze_state is ProductionGoLiveFreezeState.FROZEN:
        return "Live-provider traffic is currently frozen at the allowlisted-disabled rollout state pending further production review."
    if provider_rollback_state is ProductionGoLiveRollbackState.RECOMMENDED:
        return (
            "Live-provider traffic remains review-required; rollback is currently recommended to "
            f"`{provider_rollback_target_state}` before treating the path as production-approved."
        )
    return (
        "Live-provider traffic is active, and rollback remains available to "
        f"`{provider_rollback_target_state}` if production approval needs to be withdrawn."
    )
