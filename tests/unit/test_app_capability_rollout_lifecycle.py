from app.services.app_capability_rollout_lifecycle import (
    build_app_capability_rollout_catalog_lifecycle_status,
    build_app_capability_rollout_lifecycle_status,
)


def test_build_app_capability_rollout_lifecycle_status_distinguishes_ready_and_blocked_pairings() -> (
    None
):
    lotus_performance = build_app_capability_rollout_lifecycle_status(
        downstream_app="lotus-performance",
        capability_pack_id="analytics_commentary.pack.v1",
    )
    lotus_manage = build_app_capability_rollout_lifecycle_status(
        downstream_app="lotus-manage",
        capability_pack_id="analytics_commentary.pack.v1",
    )

    assert lotus_performance.lifecycle_ready is True
    assert lotus_performance.retirement_ready_now is True
    assert lotus_performance.historical_traceability_ready is True
    assert lotus_performance.retirement_scope.value == "PAIRING_WITH_GLOBAL_PACK_REVIEW"
    assert len(lotus_performance.retirement_rationale_summary) == 2
    assert any(item.item_id == "retirement_transition_path" for item in lotus_performance.items)
    assert any(
        item.item_id == "downstream_cleanup_boundary" and item.status == "NOT_READY"
        for item in lotus_manage.items
    )
    assert lotus_manage.lifecycle_ready is False
    assert lotus_manage.retirement_ready_now is False
    assert lotus_manage.retirement_scope.value == "PAIRING_WITH_GLOBAL_PACK_REVIEW"


def test_build_app_capability_rollout_catalog_lifecycle_status_summarizes_pairings() -> None:
    status = build_app_capability_rollout_catalog_lifecycle_status()

    assert status.ready_pairing_count == 1
    assert status.blocking_pairing_count == 3
    assert status.lifecycle_ready is False
    assert status.pairing_summaries[0].downstream_app == "lotus-performance"
    assert status.pairing_summaries[0].retirement_scope.value == "PAIRING_WITH_GLOBAL_PACK_REVIEW"
