from _pytest.monkeypatch import MonkeyPatch

from app.contracts.app_capability_rollouts import (
    AppCapabilityRolloutDescriptor,
    AppCapabilityRolloutStage,
)
from app.contracts.capability_packs import CapabilityPackMaturityStage
from app.services.app_capability_rollout_catalog import (
    _build_not_onboarded_record,
    _build_transition_targets,
    _resolve_lotus_performance_rollout_stage,
    build_app_capability_rollout_catalog,
)


def test_build_app_capability_rollout_catalog_distinguishes_pack_maturity_from_app_stage() -> None:
    catalog = build_app_capability_rollout_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.phase == "foundation"
    assert catalog.pairing_count == 4
    assert catalog.onboarded_pairing_count == 1
    assert catalog.active_pairing_count == 0
    assert catalog.downstream_app_count == 4

    rollout_by_app = {
        (record.downstream_app, record.capability_pack_id): record
        for record in catalog.rollout_records
    }
    lotus_performance = rollout_by_app[("lotus-performance", "analytics_commentary.pack.v1")]
    lotus_manage = rollout_by_app[("lotus-manage", "analytics_commentary.pack.v1")]
    lotus_advise = rollout_by_app[("lotus-advise", "decision_explanation.pack.v1")]

    assert lotus_performance.capability_pack_maturity_stage.value == "REUSABLE"
    assert lotus_performance.rollout_stage.value == "INTEGRATION_IN_PROGRESS"
    assert lotus_performance.currently_onboarded is True
    assert (
        lotus_performance.rollout_review_surface
        == "/platform/use-cases/first-production-use-case/governance-status"
    )
    assert lotus_manage.capability_pack_maturity_stage.value == "REUSABLE"
    assert lotus_manage.rollout_stage.value == "NOT_ONBOARDED"
    assert lotus_manage.currently_onboarded is False
    assert lotus_advise.capability_pack_maturity_stage.value == "EXPERIMENTAL"
    assert lotus_advise.rollout_stage.value == "NOT_ONBOARDED"


def test_resolve_lotus_performance_rollout_stage_handles_active_and_limited_states() -> None:
    assert (
        _resolve_lotus_performance_rollout_stage(
            limited_rollout_ready=False,
            active_production_ready=True,
        ).value
        == "ACTIVE_PRODUCTION"
    )
    assert (
        _resolve_lotus_performance_rollout_stage(
            limited_rollout_ready=True,
            active_production_ready=False,
        ).value
        == "LIMITED_ROLLOUT"
    )


def test_build_transition_targets_covers_later_lifecycle_states() -> None:
    active_record = AppCapabilityRolloutDescriptor(
        downstream_app="lotus-performance",
        capability_pack_id="analytics_commentary.pack.v1",
        capability_pack_family_id="analytics_commentary",
        capability_pack_maturity_stage=CapabilityPackMaturityStage.REUSABLE,
        rollout_stage=AppCapabilityRolloutStage.ACTIVE_PRODUCTION,
        currently_onboarded=True,
        current_anchor_use_case_id="lotus_performance.analytics_commentary.v1",
        rollout_review_surface="/platform/use-cases/first-production-use-case/governance-status",
        status_summary=["active"],
    )
    paused_record = AppCapabilityRolloutDescriptor(
        downstream_app="lotus-manage",
        capability_pack_id="analytics_commentary.pack.v1",
        capability_pack_family_id="analytics_commentary",
        capability_pack_maturity_stage=CapabilityPackMaturityStage.REUSABLE,
        rollout_stage=AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK,
        currently_onboarded=False,
        current_anchor_use_case_id=None,
        rollout_review_surface="/platform/capability-packs/analytics_commentary.pack.v1/adoption-template",
        status_summary=["paused"],
    )
    retired_record = AppCapabilityRolloutDescriptor(
        downstream_app="lotus-risk",
        capability_pack_id="analytics_commentary.pack.v1",
        capability_pack_family_id="analytics_commentary",
        capability_pack_maturity_stage=CapabilityPackMaturityStage.REUSABLE,
        rollout_stage=AppCapabilityRolloutStage.RETIRED,
        currently_onboarded=False,
        current_anchor_use_case_id=None,
        rollout_review_surface="/platform/capability-packs/analytics_commentary.pack.v1/adoption-template",
        status_summary=["retired"],
    )

    active_targets = _build_transition_targets(record=active_record)
    paused_targets = _build_transition_targets(record=paused_record)
    retired_targets = _build_transition_targets(record=retired_record)

    assert {target.target_stage.value for target in active_targets} == {
        "PAUSED_OR_ROLLED_BACK",
        "RETIRED",
    }
    assert {target.target_stage.value for target in paused_targets} == {
        "INTEGRATION_IN_PROGRESS",
        "RETIRED",
    }
    assert retired_targets == []


def test_build_not_onboarded_record_rejects_missing_pack(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.app_capability_rollout_catalog.get_capability_pack_by_id",
        lambda pack_id: None,
    )

    try:
        _build_not_onboarded_record(
            downstream_app="lotus-manage",
            pack_id="missing.pack.v1",
            rollout_review_surface="/platform/capability-packs/missing.pack.v1/adoption-template",
            summary="missing",
        )
    except RuntimeError as exc:
        assert "missing.pack.v1 capability pack is not registered" in str(exc)
    else:
        raise AssertionError("Expected missing pack to raise a RuntimeError")
