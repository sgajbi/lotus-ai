from __future__ import annotations

from app.config import settings
from app.contracts.app_capability_rollouts import (
    AppCapabilityLifecycleItem,
    AppCapabilityRetirementScope,
    AppCapabilityRolloutDetailResponse,
    AppCapabilityRolloutCatalogLifecycleStatusResponse,
    AppCapabilityRolloutObservabilityItem,
    AppCapabilityRolloutLifecycleStatusResponse,
    AppCapabilityRolloutLifecycleSummaryItem,
    AppCapabilityRolloutStage,
)
from app.services.app_capability_rollout_catalog import (
    build_app_capability_rollout_catalog,
    build_app_capability_rollout_detail,
    build_app_capability_rollout_governance_status,
)
from app.services.app_capability_rollout_observability import (
    build_app_capability_rollout_observability_summary,
)


def build_app_capability_rollout_lifecycle_status(
    *, downstream_app: str, capability_pack_id: str, app_state: object | None = None
) -> AppCapabilityRolloutLifecycleStatusResponse:
    detail = build_app_capability_rollout_detail(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
    )
    governance = build_app_capability_rollout_governance_status(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
    )
    observability = _get_pairing_observability_item(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
    )
    items = _build_lifecycle_items(
        detail=detail,
        governance_ready=governance.governance_ready,
        historical_traceability_ready=observability.governance_ready
        or len(observability.linked_endpoints) >= 3,
        linked_endpoint_count=len(observability.linked_endpoints),
    )
    lifecycle_ready = all(item.status == "READY" for item in items if item.required_for_retirement)
    historical_traceability_ready = any(
        item.item_id == "historical_traceability_surface" and item.status == "READY"
        for item in items
    )
    retirement_ready_now = (
        any(
            transition.target_stage is AppCapabilityRolloutStage.RETIRED and transition.allowed_now
            for transition in detail.transition_targets
        )
        and lifecycle_ready
    )
    return AppCapabilityRolloutLifecycleStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        record=detail.record,
        lifecycle_ready=lifecycle_ready,
        retirement_ready_now=retirement_ready_now,
        historical_traceability_ready=historical_traceability_ready,
        retirement_scope=_resolve_retirement_scope(detail.record.capability_pack_id),
        retirement_rationale_summary=_build_retirement_rationale_summary(detail=detail),
        traceability_endpoints=observability.linked_endpoints,
        items=items,
        status_summary=[
            (
                "The app-capability pairing currently satisfies bounded lifecycle discipline for pause, rollback, and retirement."
                if lifecycle_ready
                else "The app-capability pairing remains blocked in lifecycle review until cleanup ownership, retirement path, and traceability surfaces are all explicit."
            ),
            (
                "Retirement is immediately supportable for the current pairing."
                if retirement_ready_now
                else "Retirement remains modeled but not yet safely executable for the current pairing."
            ),
        ],
    )


def build_app_capability_rollout_catalog_lifecycle_status(
    app_state: object | None = None,
) -> AppCapabilityRolloutCatalogLifecycleStatusResponse:
    catalog = build_app_capability_rollout_catalog(app_state)
    summaries: list[AppCapabilityRolloutLifecycleSummaryItem] = []
    ready_pairing_count = 0
    for record in catalog.rollout_records:
        lifecycle = build_app_capability_rollout_lifecycle_status(
            downstream_app=record.downstream_app,
            capability_pack_id=record.capability_pack_id,
            app_state=app_state,
        )
        if lifecycle.lifecycle_ready:
            ready_pairing_count += 1
        summaries.append(
            AppCapabilityRolloutLifecycleSummaryItem(
                downstream_app=record.downstream_app,
                capability_pack_id=record.capability_pack_id,
                rollout_stage=record.rollout_stage,
                lifecycle_ready=lifecycle.lifecycle_ready,
                retirement_ready_now=lifecycle.retirement_ready_now,
                historical_traceability_ready=lifecycle.historical_traceability_ready,
                retirement_scope=lifecycle.retirement_scope,
            )
        )
    blocking_pairing_count = len(summaries) - ready_pairing_count
    return AppCapabilityRolloutCatalogLifecycleStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        lifecycle_ready=blocking_pairing_count == 0,
        ready_pairing_count=ready_pairing_count,
        blocking_pairing_count=blocking_pairing_count,
        pairing_summaries=summaries,
        status_summary=[
            (
                "All currently modeled app-capability pairings satisfy bounded lifecycle discipline."
                if blocking_pairing_count == 0
                else f"{blocking_pairing_count} currently modeled app-capability pairing(s) remain blocked in lifecycle review."
            )
        ],
    )


def _build_lifecycle_items(
    *,
    detail: AppCapabilityRolloutDetailResponse,
    governance_ready: bool,
    historical_traceability_ready: bool,
    linked_endpoint_count: int,
) -> list[AppCapabilityLifecycleItem]:
    has_retirement_transition = any(
        transition.target_stage is AppCapabilityRolloutStage.RETIRED
        for transition in detail.transition_targets
    )
    downstream_cleanup_ready = any(
        boundary.owner == detail.record.downstream_app and "tbd" not in boundary.responsibility
        for boundary in detail.ownership_boundaries
    )
    return [
        AppCapabilityLifecycleItem(
            item_id="retirement_transition_path",
            status="READY" if has_retirement_transition else "NOT_READY",
            required_for_retirement=True,
            notes="Retirement must remain an explicit lifecycle transition instead of requiring deletion or implicit archival of the pairing record.",
        ),
        AppCapabilityLifecycleItem(
            item_id="historical_traceability_surface",
            status="READY"
            if historical_traceability_ready and linked_endpoint_count >= 3
            else "NOT_READY",
            required_for_retirement=True,
            notes="Rollout review, observability review, and onboarding history must remain inspectable after pause, rollback, or retirement.",
        ),
        AppCapabilityLifecycleItem(
            item_id="downstream_cleanup_boundary",
            status="READY" if downstream_cleanup_ready else "NOT_READY",
            required_for_retirement=True,
            notes="Named downstream ownership must remain explicit so pairing retirement and cleanup do not become ambiguous between lotus-ai and the consuming app.",
        ),
        AppCapabilityLifecycleItem(
            item_id="pairing_governance_baseline",
            status="READY" if governance_ready else "NOT_READY",
            required_for_retirement=False,
            notes="Lifecycle discipline reuses the pairing governance baseline instead of defining a second ownership and escalation framework.",
        ),
    ]


def _get_pairing_observability_item(
    *, downstream_app: str, capability_pack_id: str, app_state: object | None = None
) -> AppCapabilityRolloutObservabilityItem:
    summary = build_app_capability_rollout_observability_summary(app_state)
    return next(
        item
        for item in summary.items
        if item.downstream_app == downstream_app and item.capability_pack_id == capability_pack_id
    )


def _resolve_retirement_scope(capability_pack_id: str) -> AppCapabilityRetirementScope:
    if capability_pack_id == "analytics_commentary.pack.v1":
        return AppCapabilityRetirementScope.PAIRING_WITH_GLOBAL_PACK_REVIEW
    return AppCapabilityRetirementScope.PAIRING_ONLY


def _build_retirement_rationale_summary(*, detail: AppCapabilityRolloutDetailResponse) -> list[str]:
    if detail.record.downstream_app == "lotus-performance":
        return [
            "Retiring the lotus-performance pairing would remove the current reference integration for the analytics-commentary family and should trigger broader pack-adoption review.",
            "Rollout, onboarding, and observability surfaces remain the preserved rationale path instead of relying on undocumented operator memory.",
        ]
    return [
        "Retirement should preserve why the candidate pairing was superseded, paused indefinitely, or intentionally not pursued beyond onboarding review.",
        "Because the pairing is not the current reference integration, retirement can remain pairing-scoped unless broader capability-pack review is triggered separately.",
    ]
