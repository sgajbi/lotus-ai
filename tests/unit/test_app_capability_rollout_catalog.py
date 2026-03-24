from app.services.app_capability_rollout_catalog import build_app_capability_rollout_catalog


def test_build_app_capability_rollout_catalog_distinguishes_pack_maturity_from_app_stage() -> (
    None
):
    catalog = build_app_capability_rollout_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.phase == "foundation"
    assert catalog.pairing_count == 4
    assert catalog.onboarded_pairing_count == 1
    assert catalog.active_pairing_count == 0
    assert catalog.downstream_app_count == 4

    rollout_by_app = {
        (record.downstream_app, record.capability_pack_id): record for record in catalog.rollout_records
    }
    lotus_performance = rollout_by_app[
        ("lotus-performance", "analytics_commentary.pack.v1")
    ]
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
