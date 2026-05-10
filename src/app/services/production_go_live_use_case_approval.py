from __future__ import annotations

from app.config import settings
from app.contracts.capability_packs import CapabilityPackGovernanceStatusResponse
from app.contracts.production_go_live import (
    ProductionGoLiveFreezeState,
    ProductionGoLiveRuntimeStatusResponse,
    ProductionGoLiveUseCaseApprovalItem,
    ProductionGoLiveUseCaseApprovalResponse,
    ProductionGoLiveUseCaseApprovalState,
)
from app.contracts.providers import ProviderGovernanceStatusResponse
from app.contracts.use_cases import (
    FirstUseCaseGovernanceStatusResponse,
    FirstUseCaseRuntimeStatusResponse,
)
from app.services.capability_pack_governance import build_capability_pack_governance_status
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.first_use_case_status import build_first_use_case_runtime_status
from app.services.governance_readiness import summarize_activation_items
from app.services.production_go_live_runtime import build_production_go_live_runtime_status
from app.services.provider_governance_status import build_provider_governance_status


def build_production_go_live_use_case_approval(
    app_state: object | None = None,
    *,
    use_case_status: FirstUseCaseRuntimeStatusResponse | None = None,
    use_case_governance: FirstUseCaseGovernanceStatusResponse | None = None,
    pack_governance: CapabilityPackGovernanceStatusResponse | None = None,
    provider_governance: ProviderGovernanceStatusResponse | None = None,
    runtime_status: ProductionGoLiveRuntimeStatusResponse | None = None,
) -> ProductionGoLiveUseCaseApprovalResponse:
    use_case_status = (
        use_case_status if use_case_status is not None else build_first_use_case_runtime_status()
    )
    use_case_governance = (
        use_case_governance
        if use_case_governance is not None
        else build_first_use_case_governance_status()
    )
    pack_governance = (
        pack_governance
        if pack_governance is not None
        else build_capability_pack_governance_status(pack_id=use_case_status.capability_pack_id)
    )
    provider_governance = (
        provider_governance
        if provider_governance is not None
        else build_provider_governance_status()
    )
    runtime_status = (
        runtime_status
        if runtime_status is not None
        else build_production_go_live_runtime_status(app_state)
    )

    live_provider_active = (
        runtime_status.provider_freeze_state is ProductionGoLiveFreezeState.ACTIVE
    )
    items = [
        ProductionGoLiveUseCaseApprovalItem(
            item_id="first_use_case_limited_rollout_governance",
            status="READY" if use_case_governance.governance_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "The named first use case must already be governance-ready for bounded limited rollout before active production can be approved."
            ),
        ),
        ProductionGoLiveUseCaseApprovalItem(
            item_id="capability_pack_governance",
            status="READY" if pack_governance.governance_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "The anchoring capability pack must satisfy activation, runbook, and observability governance before the downstream use case can inherit active-production approval."
            ),
        ),
        ProductionGoLiveUseCaseApprovalItem(
            item_id="platform_production_approval",
            status="READY" if runtime_status.platform_production_approved else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Platform production approval must already be satisfied before the downstream use case can move beyond limited rollout."
            ),
        ),
        ProductionGoLiveUseCaseApprovalItem(
            item_id="live_provider_governance",
            status="READY" if provider_governance.governance_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider governance must remain ready so active-production traffic does not rely on technical live execution alone."
            ),
        ),
        ProductionGoLiveUseCaseApprovalItem(
            item_id="live_provider_active_rollout",
            status="READY" if live_provider_active else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Active production requires live-provider traffic to remain in an approved active rollout posture rather than a frozen, review-required, or non-live state."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    limited_rollout_ready = use_case_governance.governance_ready
    active_production_ready = completed_required_item_count == required_item_count
    approval_state = _resolve_use_case_approval_state(
        limited_rollout_ready=limited_rollout_ready,
        active_production_ready=active_production_ready,
        platform_production_approved=runtime_status.platform_production_approved,
    )

    return ProductionGoLiveUseCaseApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        use_case_id=use_case_status.use_case_id,
        downstream_app=use_case_status.downstream_app,
        capability_pack_id=use_case_status.capability_pack_id,
        approval_state=approval_state,
        limited_rollout_ready=limited_rollout_ready,
        active_production_ready=active_production_ready,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
        status_summary=[
            (
                "The named downstream use case is approved for active production traffic."
                if active_production_ready
                else "The named downstream use case is not yet approved for active production traffic."
            ),
            (
                "Limited rollout is already ready, so the remaining gap is the stricter active-production boundary."
                if limited_rollout_ready and not active_production_ready
                else "Limited rollout is not yet ready, so active-production approval remains out of reach."
            ),
            (
                "The active-production decision is now derived from first-use-case governance, capability-pack governance, platform approval, and live-provider production posture together."
            ),
        ],
    )


def _resolve_use_case_approval_state(
    *,
    limited_rollout_ready: bool,
    active_production_ready: bool,
    platform_production_approved: bool,
) -> ProductionGoLiveUseCaseApprovalState:
    if active_production_ready:
        return ProductionGoLiveUseCaseApprovalState.PRODUCTION_APPROVED
    if limited_rollout_ready and not platform_production_approved:
        return ProductionGoLiveUseCaseApprovalState.LIMITED_ROLLOUT_READY
    if limited_rollout_ready:
        return ProductionGoLiveUseCaseApprovalState.PRODUCTION_BLOCKED
    return ProductionGoLiveUseCaseApprovalState.PRE_PROD_VALIDATION
