from app.services.capability_pack_adoption_template import (
    build_capability_pack_adoption_template,
)


def test_build_capability_pack_adoption_template_for_analytics_commentary() -> None:
    template = build_capability_pack_adoption_template("analytics_commentary.pack.v1")

    assert template.template_id == "analytics_commentary.pack.v1.adoption-template.v1"
    assert template.pack_id == "analytics_commentary.pack.v1"
    assert template.current_reference_use_case_id == "lotus_performance.analytics_commentary.v1"
    assert "lotus-performance" in template.recommended_caller_apps
    assert any(
        item.checklist_id == "pack_contract_adopted" and item.required
        for item in template.checklist
    )
    assert any(
        criterion.criterion_id == "pack_governance_ready"
        and criterion.evaluation_surface
        == "/platform/capability-packs/analytics_commentary.pack.v1/governance-status"
        for criterion in template.approval_criteria
    )


def test_build_capability_pack_adoption_template_for_decision_explanation() -> None:
    template = build_capability_pack_adoption_template("decision_explanation.pack.v1")

    assert template.pack_id == "decision_explanation.pack.v1"
    assert template.current_reference_use_case_id is None
    assert "lotus-manage" in template.recommended_caller_apps
    assert any(
        item.checklist_id == "deterministic_decision_owner_defined" for item in template.checklist
    )
    assert any(
        "lacks a concrete implemented downstream anchor" in line for line in template.status_summary
    )


def test_build_capability_pack_adoption_template_rejects_unknown_pack() -> None:
    try:
        build_capability_pack_adoption_template("unknown.pack")
    except ValueError as exc:
        assert "Unknown capability pack" in str(exc)
    else:
        raise AssertionError("Expected unknown capability pack lookup to fail")
