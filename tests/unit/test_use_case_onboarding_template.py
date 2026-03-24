from app.services.use_case_onboarding_template import build_use_case_onboarding_template


def test_use_case_onboarding_template_describes_reusable_bounded_pattern() -> None:
    template = build_use_case_onboarding_template()

    assert template.template_id == "bounded_explanation_only_onboarding.v1"
    assert template.based_on_use_case_id == "lotus_performance.analytics_commentary.v1"
    assert any(item.checklist_id == "contract_boundary_defined" for item in template.checklist)
    assert any(
        criterion.criterion_id == "approval_governance_summary"
        for criterion in template.approval_criteria
    )
    assert any("support-review surfaces" in lesson for lesson in template.lessons_learned)
