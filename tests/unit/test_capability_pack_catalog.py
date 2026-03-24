from app.contracts.capability_packs import CapabilityPackMaturityStage
from app.services.capability_pack_catalog import (
    build_capability_pack_catalog,
    build_capability_pack_detail,
)


def test_build_capability_pack_catalog_exposes_separate_product_layer() -> None:
    catalog = build_capability_pack_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.phase == "foundation"
    assert catalog.pack_count == 2
    assert catalog.reusable_pack_count == 1
    assert catalog.approved_pack_count == 0
    assert catalog.packs[0].pack_id == "analytics_commentary.pack.v1"
    assert catalog.packs[0].family_id == "analytics_commentary"
    assert catalog.packs[0].maturity_stage == CapabilityPackMaturityStage.REUSABLE
    assert catalog.packs[0].primary_task_id == "explain.v1"
    assert (
        catalog.packs[0].current_anchor_use_case_id == "lotus_performance.analytics_commentary.v1"
    )
    assert catalog.packs[0].reusable_across_apps is True
    assert catalog.packs[0].quality_gate_domain_id == "analytics_commentary_pack"
    assert catalog.packs[0].quality_gate_ready is False
    assert catalog.packs[0].quality_evidence_state.value == "STAGED_ONLY"
    assert (
        catalog.packs[0].adoption_template_endpoint
        == "/platform/capability-packs/analytics_commentary.pack.v1/adoption-template"
    )
    assert catalog.packs[1].pack_id == "decision_explanation.pack.v1"
    assert catalog.packs[1].family_id == "decision_explanation"
    assert catalog.packs[1].current_anchor_use_case_id is None
    assert catalog.packs[1].quality_gate_domain_id == "decision_explanation_pack"


def test_build_capability_pack_catalog_links_pack_governance_surfaces() -> None:
    catalog = build_capability_pack_catalog()
    pack = catalog.packs[0]

    assert "/platform/capability-packs" in pack.governance_surface_ids
    assert "/platform/capability-packs/analytics_commentary.pack.v1/adoption-template" in (
        pack.governance_surface_ids
    )
    assert "/platform/use-cases/first-production-use-case" in pack.governance_surface_ids
    assert (
        "/platform/use-cases/first-production-use-case/governance-status"
        in pack.governance_surface_ids
    )
    assert any("separate app-facing product layer" in line for line in catalog.status_summary)


def test_build_capability_pack_detail_exposes_quality_and_input_boundaries() -> None:
    detail = build_capability_pack_detail("analytics_commentary.pack.v1")

    assert detail.pack.pack_id == "analytics_commentary.pack.v1"
    assert detail.approval_gate.domain_id == "analytics_commentary_pack"
    assert detail.approval_gate.evidence_state.value == "STAGED_ONLY"
    assert len(detail.quality_expectations) == 3
    assert any(
        expectation.expectation_id == "grounded_to_caller_facts"
        for expectation in detail.quality_expectations
    )
    assert any(
        behavior.behavior_id == "missing_metric_deltas"
        for behavior in detail.unsupported_input_behaviors
    )
    assert any("broader reusable product family" in line for line in detail.status_summary)


def test_build_capability_pack_detail_supports_decision_explanation_family() -> None:
    detail = build_capability_pack_detail("decision_explanation.pack.v1")

    assert detail.pack.family_id == "decision_explanation"
    assert detail.pack.current_anchor_use_case_id is None
    assert detail.approval_gate.domain_id == "decision_explanation_pack"
    assert any(
        expectation.expectation_id == "grounded_to_deterministic_state"
        for expectation in detail.quality_expectations
    )
    assert any(
        behavior.behavior_id == "missing_decision_state"
        for behavior in detail.unsupported_input_behaviors
    )


def test_build_capability_pack_detail_reports_runtime_quality_gate_pass() -> None:
    from app.contracts.evals import EvaluationRunSubmissionRequest
    from app.services.eval_async_execution import run_next_evaluation_execution_job
    from app.services.eval_run_submission_service import submit_evaluation_run

    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="capability_pack_analytics_commentary_examples",
            caller_app="lotus-platform",
            correlation_id="corr-pack-quality-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    detail = build_capability_pack_detail("analytics_commentary.pack.v1")

    assert detail.approval_gate.approval_ready is True
    assert detail.approval_gate.evidence_state.value == "RUNTIME_PASS"
    assert detail.pack.quality_gate_ready is True


def test_build_capability_pack_detail_rejects_unknown_pack() -> None:
    try:
        build_capability_pack_detail("unknown.pack")
    except ValueError as exc:
        assert "Unknown capability pack" in str(exc)
    else:
        raise AssertionError("Expected unknown capability pack lookup to fail")
