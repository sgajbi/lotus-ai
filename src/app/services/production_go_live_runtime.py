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
from app.contracts.production_baseline import ProductionBaselineRuntimeStatusResponse
from app.contracts.prompts import PromptGovernanceStatusSummaryResponse
from app.contracts.providers import ProviderGovernanceStatusResponse, ProviderRolloutState
from app.contracts.retrieval import RetrievalGovernanceStatusResponse
from app.contracts.safety import SafetyGovernanceStatusResponse
from app.contracts.use_cases import FirstUseCaseGovernanceStatusResponse
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status
from app.services.production_go_live_approval_domains import (
    build_managed_object_storage_approval_domain,
    build_managed_secret_approval_domain,
)
from app.services.production_live_provider_inventory import build_live_provider_inventory
from app.services.prompt_governance_status import build_prompt_governance_status_summary
from app.services.provider_governance_status import build_provider_governance_status
from app.services.retrieval_governance_status import build_retrieval_governance_status
from app.services.safety_governance_status import build_safety_governance_status


def build_production_go_live_runtime_status(
    app_state: object | None = None,
    *,
    baseline: ProductionBaselineRuntimeStatusResponse | None = None,
    provider_governance: ProviderGovernanceStatusResponse | None = None,
    first_use_case_governance: FirstUseCaseGovernanceStatusResponse | None = None,
    retrieval_governance: RetrievalGovernanceStatusResponse | None = None,
    prompt_governance: PromptGovernanceStatusSummaryResponse | None = None,
    safety_governance: SafetyGovernanceStatusResponse | None = None,
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
    retrieval_governance = (
        retrieval_governance
        if retrieval_governance is not None
        else build_retrieval_governance_status()
    )
    live_provider_inventory = build_live_provider_inventory()
    live_provider_required = live_provider_inventory.execution_requested
    retrieval_required = settings.retrieval_mode == "enabled"
    prompt_governance_required = _live_prompt_activation_required()
    safety_governance_required = settings.safety_mode == "runtime_enforced"
    prompt_governance = _resolve_prompt_governance(
        prompt_governance=prompt_governance,
        required_for_platform_approval=prompt_governance_required,
    )
    safety_governance = _resolve_safety_governance(
        safety_governance=safety_governance,
        required_for_platform_approval=safety_governance_required,
    )
    prompt_governance_ready = _optional_governance_ready(prompt_governance)
    safety_governance_ready = _optional_governance_ready(safety_governance)
    managed_secret = build_managed_secret_approval_domain()
    managed_object_store = build_managed_object_storage_approval_domain()

    approval_domains = [
        managed_secret,
        managed_object_store,
        ProductionGoLiveDomainDescriptor(
            domain_id="live_provider_governance",
            status=_provider_domain_status(
                governance_ready=provider_governance.governance_ready,
                required_for_platform_approval=live_provider_required,
            ),
            required_for_platform_approval=live_provider_required,
            configured_mode=live_provider_inventory.configured_mode_summary,
            review_surface="/platform/providers/governance-status",
            detail=(
                "Live-provider governance is currently ready for the configured provider posture covering "
                f"{', '.join(live_provider_inventory.execution_capability_labels)}."
                if provider_governance.governance_ready
                else (
                    "Live-provider execution is requested for "
                    f"{', '.join(live_provider_inventory.execution_capability_labels)}, but provider governance is not yet approved for production go-live."
                    if live_provider_required
                    else "Live-provider execution is not requested in the current runtime posture."
                )
            ),
        ),
        ProductionGoLiveDomainDescriptor(
            domain_id="retrieval_governance",
            status=_retrieval_domain_status(
                governance_ready=retrieval_governance.governance_ready,
                required_for_platform_approval=retrieval_required,
            ),
            required_for_platform_approval=retrieval_required,
            configured_mode=settings.retrieval_mode,
            review_surface="/platform/retrieval/governance-status",
            detail=(
                "Retrieval governance is currently approved for active retrieval execution."
                if retrieval_governance.governance_ready
                else (
                    "Retrieval execution is enabled, but runtime-backed retrieval governance and evaluation evidence are not yet approved for production go-live."
                    if retrieval_required
                    else "Retrieval execution is disabled or outside the current production route, so retrieval governance is informational for production go-live."
                )
            ),
        ),
        ProductionGoLiveDomainDescriptor(
            domain_id="prompt_governance",
            status=_active_control_domain_status(
                governance_ready=prompt_governance_ready,
                required_for_platform_approval=prompt_governance_required,
            ),
            required_for_platform_approval=prompt_governance_required,
            configured_mode=_prompt_governance_configured_mode(),
            review_surface="/platform/prompts/governance-status",
            detail=_prompt_governance_domain_detail(
                governance_ready=prompt_governance_ready,
                required_for_platform_approval=prompt_governance_required,
            ),
        ),
        ProductionGoLiveDomainDescriptor(
            domain_id="safety_governance",
            status=_active_control_domain_status(
                governance_ready=safety_governance_ready,
                required_for_platform_approval=safety_governance_required,
            ),
            required_for_platform_approval=safety_governance_required,
            configured_mode=settings.safety_mode,
            review_surface="/platform/safety/governance-status",
            detail=_safety_governance_domain_detail(
                governance_ready=safety_governance_ready,
                required_for_platform_approval=safety_governance_required,
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
        and (not live_provider_required or provider_governance.governance_ready)
        and (not retrieval_required or retrieval_governance.governance_ready)
        and (not prompt_governance_required or prompt_governance_ready)
        and (not safety_governance_required or safety_governance_ready)
    )
    use_case_production_approved = first_use_case_governance.active_production_ready
    provider_freeze_state = _resolve_provider_freeze_state(
        live_provider_required=live_provider_required,
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
                else "Platform production approval remains blocked pending required approval domains."
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


def _provider_domain_status(
    *, governance_ready: bool, required_for_platform_approval: bool
) -> ProductionGoLiveDomainStatus:
    if governance_ready:
        return ProductionGoLiveDomainStatus.APPROVED
    if required_for_platform_approval:
        return ProductionGoLiveDomainStatus.BLOCKED
    return ProductionGoLiveDomainStatus.INFORMATIONAL


def _retrieval_domain_status(
    *, governance_ready: bool, required_for_platform_approval: bool
) -> ProductionGoLiveDomainStatus:
    if governance_ready:
        return ProductionGoLiveDomainStatus.APPROVED
    if required_for_platform_approval:
        return ProductionGoLiveDomainStatus.BLOCKED
    return ProductionGoLiveDomainStatus.INFORMATIONAL


def _active_control_domain_status(
    *, governance_ready: bool, required_for_platform_approval: bool
) -> ProductionGoLiveDomainStatus:
    if not required_for_platform_approval:
        return ProductionGoLiveDomainStatus.INFORMATIONAL
    if governance_ready:
        return ProductionGoLiveDomainStatus.APPROVED
    return ProductionGoLiveDomainStatus.BLOCKED


def _optional_governance_ready(
    governance: PromptGovernanceStatusSummaryResponse | SafetyGovernanceStatusResponse | None,
) -> bool:
    return bool(governance and governance.governance_ready)


def _resolve_prompt_governance(
    *,
    prompt_governance: PromptGovernanceStatusSummaryResponse | None,
    required_for_platform_approval: bool,
) -> PromptGovernanceStatusSummaryResponse | None:
    if prompt_governance is not None:
        return prompt_governance
    if required_for_platform_approval:
        return build_prompt_governance_status_summary()
    return None


def _resolve_safety_governance(
    *,
    safety_governance: SafetyGovernanceStatusResponse | None,
    required_for_platform_approval: bool,
) -> SafetyGovernanceStatusResponse | None:
    if safety_governance is not None:
        return safety_governance
    if required_for_platform_approval:
        return build_safety_governance_status()
    return None


def _live_prompt_activation_required() -> bool:
    return (
        settings.prompt_store_mode == "sqlalchemy"
        and settings.evaluation_runtime_store_mode == "sqlalchemy"
    )


def _prompt_governance_configured_mode() -> str:
    return (
        f"prompt_store={settings.prompt_store_mode}; "
        f"evaluation_runtime_store={settings.evaluation_runtime_store_mode}"
    )


def _prompt_governance_domain_detail(
    *, governance_ready: bool, required_for_platform_approval: bool
) -> str:
    if not required_for_platform_approval:
        return (
            "Live prompt activation is not enabled through both SQL-backed prompt and evaluation-runtime stores, "
            "so prompt governance remains informational for production go-live."
        )
    if governance_ready:
        return (
            "Live prompt activation is enabled through SQL-backed prompt and evaluation-runtime stores, "
            "and prompt governance is approved for production go-live."
        )
    return (
        "Live prompt activation is enabled through SQL-backed prompt and evaluation-runtime stores, "
        "but prompt governance is not yet approved for production go-live."
    )


def _safety_governance_domain_detail(
    *, governance_ready: bool, required_for_platform_approval: bool
) -> str:
    if not required_for_platform_approval:
        return (
            "Runtime safety enforcement is not active, so safety governance remains informational for production go-live."
        )
    if governance_ready:
        return (
            "Runtime safety enforcement is active, and safety governance is approved for production go-live."
        )
    return (
        "Runtime safety enforcement is active, but safety governance is not yet approved for production go-live."
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
    *, live_provider_required: bool, rollout_state: str, provider_governance_ready: bool
) -> ProductionGoLiveFreezeState:
    if not live_provider_required:
        return ProductionGoLiveFreezeState.NOT_APPLICABLE
    if rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED.value:
        return ProductionGoLiveFreezeState.FROZEN
    if not provider_governance_ready:
        return ProductionGoLiveFreezeState.REVIEW_REQUIRED
    if rollout_state in {
        ProviderRolloutState.DOCUMENTED_ONLY.value,
        ProviderRolloutState.STUB_DEFAULT.value,
    }:
        return ProductionGoLiveFreezeState.NOT_APPLICABLE
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
