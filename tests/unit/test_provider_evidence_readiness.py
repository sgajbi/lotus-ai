from app.services.provider_evidence_readiness import build_provider_evidence_readiness


def test_provider_evidence_readiness_reports_foundation_evidence_gaps() -> None:
    readiness = build_provider_evidence_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.evidence_ready is False
    assert readiness.required_item_count == 9
    assert readiness.completed_required_item_count == 7
    assert readiness.items[0].evidence_id == "provider_policy_fixture_pack"
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].evidence_id == "provider_runtime_fixture_pack"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].evidence_id == "provider_failure_mode_fixture_pack"
    assert readiness.items[2].status == "READY"
    assert readiness.items[3].evidence_id == "provider_operations_fixture_pack"
    assert readiness.items[3].status == "READY"
    assert readiness.items[4].evidence_id == "provider_degradation_fixture_pack"
    assert readiness.items[4].status == "READY"
    assert readiness.items[5].evidence_id == "provider_embedding_fixture_pack"
    assert readiness.items[5].status == "READY"
    assert readiness.items[6].evidence_id == "provider_regression_run_baseline"
    assert readiness.items[6].status == "READY"
    assert readiness.items[7].status == "FOUNDATION_STAGED"
    assert readiness.items[8].status == "NOT_READY"
    assert readiness.approval_gate.domain_id == "provider_execution"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"


def test_provider_evidence_readiness_is_derived_from_its_own_counts() -> None:
    """The flag was hard-coded False while the counts were computed and then
    discarded, so the surface could not have reported readiness even once
    the evidence genuinely arrived (issue #154)."""

    readiness = build_provider_evidence_readiness()

    expected = (
        readiness.required_item_count > 0
        and readiness.completed_required_item_count == readiness.required_item_count
    )
    assert readiness.evidence_ready is expected
    # Today one required item is a documented gap, so the honest answer is
    # still False - but it is now an answer, not an assertion.
    assert readiness.evidence_ready is False
    assert readiness.completed_required_item_count < readiness.required_item_count
