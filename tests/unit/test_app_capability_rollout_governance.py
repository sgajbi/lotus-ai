from app.services.app_capability_rollout_catalog import (
    build_app_capability_rollout_catalog_governance_status,
    build_app_capability_rollout_detail,
    build_app_capability_rollout_governance_status,
    build_app_capability_onboarding_template,
)


def test_build_app_capability_rollout_detail_exposes_ownership_and_transitions() -> None:
    detail = build_app_capability_rollout_detail(
        downstream_app="lotus-performance",
        capability_pack_id="analytics_commentary.pack.v1",
    )

    assert detail.record.downstream_app == "lotus-performance"
    assert any(boundary.owner == "lotus-ai" for boundary in detail.ownership_boundaries)
    assert any(boundary.owner == "lotus-performance" for boundary in detail.ownership_boundaries)
    assert any(path.escalation_id == "shared_rollout_review" for path in detail.escalation_paths)
    assert any(
        transition.target_stage.value == "LIMITED_ROLLOUT"
        for transition in detail.transition_targets
    )
    assert any(
        transition.target_stage.value == "PAUSED_OR_ROLLED_BACK"
        for transition in detail.transition_targets
    )


def test_build_app_capability_rollout_governance_status_distinguishes_ready_and_blocked_pairings() -> (
    None
):
    lotus_performance = build_app_capability_rollout_governance_status(
        downstream_app="lotus-performance",
        capability_pack_id="analytics_commentary.pack.v1",
    )
    lotus_manage = build_app_capability_rollout_governance_status(
        downstream_app="lotus-manage",
        capability_pack_id="analytics_commentary.pack.v1",
    )

    assert lotus_performance.governance_ready is True
    assert lotus_performance.blocking_area_count == 0
    assert lotus_manage.governance_ready is False
    assert lotus_manage.blocking_area_count >= 2
    assert any(item.item_id == "downstream_owner_boundary" for item in lotus_manage.items)
    assert any(
        item.item_id == "pause_rollback_retirement_model" for item in lotus_performance.items
    )


def test_build_app_capability_rollout_catalog_governance_status_summarizes_pairings() -> None:
    status = build_app_capability_rollout_catalog_governance_status()

    assert status.ready_pairing_count == 1
    assert status.blocking_pairing_count == 3
    assert status.governance_ready is False
    assert status.pairing_summaries[0].downstream_app == "lotus-performance"


def test_build_app_capability_onboarding_template_reuses_reference_use_case_when_available() -> (
    None
):
    template = build_app_capability_onboarding_template(
        downstream_app="lotus-performance",
        capability_pack_id="analytics_commentary.pack.v1",
    )

    assert template.downstream_app == "lotus-performance"
    assert template.based_on_pack_template_id == "analytics_commentary.pack.v1.adoption-template.v1"
    assert template.reference_use_case_template_id == "bounded_explanation_only_onboarding.v1"
    assert any(
        item.checklist_id == "runtime_eval_family_staged_and_passing" for item in template.checklist
    )
    assert any(
        criterion.criterion_id == "approval_governance_summary"
        for criterion in template.approval_criteria
    )


def test_build_app_capability_onboarding_template_falls_back_to_pack_template_for_non_anchor_pairing() -> (
    None
):
    template = build_app_capability_onboarding_template(
        downstream_app="lotus-manage",
        capability_pack_id="analytics_commentary.pack.v1",
    )

    assert template.downstream_app == "lotus-manage"
    assert template.reference_use_case_template_id is None
    assert any(item.checklist_id == "pack_contract_adopted" for item in template.checklist)
    assert any(
        criterion.criterion_id == "pack_governance_ready"
        for criterion in template.approval_criteria
    )
