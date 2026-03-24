from __future__ import annotations

from app.config import settings
from app.contracts.app_capability_rollouts import (
    AppCapabilityRolloutCatalogResponse,
    AppCapabilityRolloutDescriptor,
    AppCapabilityRolloutStage,
)
from app.services.capability_pack_catalog import build_capability_pack_catalog, get_capability_pack_by_id
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.first_use_case_status import build_first_use_case_runtime_status
from app.services.production_go_live_use_case_approval import (
    build_production_go_live_use_case_approval,
)


def build_app_capability_rollout_catalog(
    app_state: object | None = None,
) -> AppCapabilityRolloutCatalogResponse:
    rollout_records = _build_rollout_records(app_state)
    onboarded_pairing_count = sum(1 for record in rollout_records if record.currently_onboarded)
    active_pairing_count = sum(
        1
        for record in rollout_records
        if record.rollout_stage
        in {
            AppCapabilityRolloutStage.LIMITED_ROLLOUT,
            AppCapabilityRolloutStage.ACTIVE_PRODUCTION,
        }
    )
    downstream_app_count = len({record.downstream_app for record in rollout_records})
    return AppCapabilityRolloutCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        pairing_count=len(rollout_records),
        onboarded_pairing_count=onboarded_pairing_count,
        active_pairing_count=active_pairing_count,
        downstream_app_count=downstream_app_count,
        rollout_records=rollout_records,
        status_summary=[
            "App-capability rollout records are now modeled separately from global capability-pack maturity so downstream rollout truth stays pairing-specific.",
            "Slice 1 is intentionally catalog-first: it exposes status and rollout-stage truth without yet introducing ownership, pause, rollback, or retirement controls.",
            "The first implemented lotus-performance pairing remains the concrete anchor while later candidate apps stay visible as not-onboarded rollout records instead of living only in RFC prose.",
        ],
    )


def _build_rollout_records(app_state: object | None) -> list[AppCapabilityRolloutDescriptor]:
    capability_catalog = build_capability_pack_catalog()
    pack_by_id = {pack.pack_id: pack for pack in capability_catalog.packs}
    first_use_case = build_first_use_case_runtime_status()
    first_use_case_governance = build_first_use_case_governance_status()
    production_go_live = build_production_go_live_use_case_approval(app_state)

    analytics_pack = pack_by_id["analytics_commentary.pack.v1"]
    decision_pack = pack_by_id["decision_explanation.pack.v1"]

    lotus_performance_stage = _resolve_lotus_performance_rollout_stage(
        limited_rollout_ready=first_use_case_governance.governance_ready,
        active_production_ready=production_go_live.active_production_ready,
    )

    return [
        AppCapabilityRolloutDescriptor(
            downstream_app=first_use_case.downstream_app,
            capability_pack_id=analytics_pack.pack_id,
            capability_pack_family_id=analytics_pack.family_id,
            capability_pack_maturity_stage=analytics_pack.maturity_stage,
            rollout_stage=lotus_performance_stage,
            currently_onboarded=True,
            current_anchor_use_case_id=first_use_case.use_case_id,
            rollout_review_surface="/platform/use-cases/first-production-use-case/governance-status",
            status_summary=[
                "Lotus-performance is the current implemented app-capability anchor for analytics commentary.",
                (
                    "The pairing is ready for bounded limited rollout."
                    if lotus_performance_stage is AppCapabilityRolloutStage.LIMITED_ROLLOUT
                    else "The pairing is still below limited-rollout approval, so it remains in governed integration posture."
                ),
            ],
        ),
        _build_not_onboarded_record(
            downstream_app="lotus-manage",
            pack_id=analytics_pack.pack_id,
            rollout_review_surface=f"/platform/capability-packs/{analytics_pack.pack_id}/adoption-template",
            summary=(
                "Lotus-manage is a likely next analytics-commentary candidate, but no governed pairing record beyond not-onboarded posture exists yet."
            ),
        ),
        _build_not_onboarded_record(
            downstream_app="lotus-risk",
            pack_id=analytics_pack.pack_id,
            rollout_review_surface=f"/platform/capability-packs/{analytics_pack.pack_id}/adoption-template",
            summary=(
                "Lotus-risk is visible as a future commentary-pack adoption target without implying that integration work has started."
            ),
        ),
        _build_not_onboarded_record(
            downstream_app="lotus-advise",
            pack_id=decision_pack.pack_id,
            rollout_review_surface=f"/platform/capability-packs/{decision_pack.pack_id}/adoption-template",
            summary=(
                "Lotus-advise is visible as a future decision-explanation-pack adoption target while the pack itself remains experimental."
            ),
        ),
    ]


def _build_not_onboarded_record(
    *,
    downstream_app: str,
    pack_id: str,
    rollout_review_surface: str,
    summary: str,
) -> AppCapabilityRolloutDescriptor:
    pack = get_capability_pack_by_id(pack_id)
    if pack is None:
        raise RuntimeError(f"{pack_id} capability pack is not registered")
    return AppCapabilityRolloutDescriptor(
        downstream_app=downstream_app,
        capability_pack_id=pack.pack_id,
        capability_pack_family_id=pack.family_id,
        capability_pack_maturity_stage=pack.maturity_stage,
        rollout_stage=AppCapabilityRolloutStage.NOT_ONBOARDED,
        currently_onboarded=False,
        current_anchor_use_case_id=None,
        rollout_review_surface=rollout_review_surface,
        status_summary=[
            summary,
            "Global pack maturity remains visible here, but this app-specific rollout record is still not onboarded.",
        ],
    )


def _resolve_lotus_performance_rollout_stage(
    *, limited_rollout_ready: bool, active_production_ready: bool
) -> AppCapabilityRolloutStage:
    if active_production_ready:
        return AppCapabilityRolloutStage.ACTIVE_PRODUCTION
    if limited_rollout_ready:
        return AppCapabilityRolloutStage.LIMITED_ROLLOUT
    return AppCapabilityRolloutStage.INTEGRATION_IN_PROGRESS
