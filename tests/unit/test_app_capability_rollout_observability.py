from app.services.app_capability_rollout_observability import (
    _matches_pairing_job,
    _matches_pairing_record,
    _resolve_estate_visibility_state,
    build_app_capability_rollout_observability_summary,
)
from app.contracts.app_capability_rollouts import AppCapabilityRolloutStage


def test_build_app_capability_rollout_observability_summary_exposes_estate_visibility() -> None:
    summary = build_app_capability_rollout_observability_summary()

    assert summary.service == "lotus-ai"
    assert summary.observability_ready is True
    assert summary.pairing_count == 4
    assert summary.active_pairing_count == 0
    assert summary.blocked_pairing_count == 4
    assert summary.paused_pairing_count == 0
    assert summary.retired_pairing_count == 0

    lotus_performance = next(
        item
        for item in summary.items
        if item.downstream_app == "lotus-performance"
        and item.capability_pack_id == "analytics_commentary.pack.v1"
    )
    lotus_advise = next(
        item
        for item in summary.items
        if item.downstream_app == "lotus-advise"
        and item.capability_pack_id == "decision_explanation.pack.v1"
    )

    assert lotus_performance.rollout_stage.value == "INTEGRATION_IN_PROGRESS"
    assert lotus_performance.estate_visibility_state.value == "BLOCKED"
    assert lotus_performance.governance_ready is True
    assert lotus_performance.sampled_audit_record_count >= 0
    assert lotus_performance.sampled_async_job_count >= 0
    assert (
        "/platform/app-capability-rollouts/lotus-performance/analytics_commentary.pack.v1"
        in lotus_performance.linked_endpoints
    )
    assert "/platform/observability/incident-summary" in lotus_performance.linked_endpoints
    assert lotus_advise.estate_visibility_state.value == "BLOCKED"
    assert lotus_advise.governance_ready is False


def test_app_capability_rollout_observability_helper_branches_cover_all_visibility_states() -> None:
    assert (
        _resolve_estate_visibility_state(
            rollout_stage=AppCapabilityRolloutStage.RETIRED,
            governance_ready=False,
        ).value
        == "RETIRED"
    )
    assert (
        _resolve_estate_visibility_state(
            rollout_stage=AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK,
            governance_ready=True,
        ).value
        == "PAUSED"
    )
    assert (
        _resolve_estate_visibility_state(
            rollout_stage=AppCapabilityRolloutStage.ACTIVE_PRODUCTION,
            governance_ready=True,
        ).value
        == "ACTIVE"
    )
    assert (
        _resolve_estate_visibility_state(
            rollout_stage=AppCapabilityRolloutStage.LIMITED_ROLLOUT,
            governance_ready=False,
        ).value
        == "BLOCKED"
    )


def test_app_capability_rollout_observability_matching_helpers_cover_supported_and_unknown_paths() -> (
    None
):
    record = type(
        "AuditRecordStub",
        (),
        {"task_id": "explain.v1", "caller_app": "lotus-manage"},
    )()
    job = type(
        "AsyncJobStub",
        (),
        {"job_type": "task_execution", "caller_app": "lotus-manage"},
    )()

    assert _matches_pairing_record(
        record=record,
        downstream_app="lotus-manage",
        capability_pack_id="decision_explanation.pack.v1",
    )
    assert _matches_pairing_job(
        job=job,
        downstream_app="lotus-manage",
        capability_pack_id="decision_explanation.pack.v1",
    )
    assert (
        _matches_pairing_record(
            record=record,
            downstream_app="lotus-manage",
            capability_pack_id="unknown.pack.v1",
        )
        is False
    )
    assert (
        _matches_pairing_job(
            job=job,
            downstream_app="lotus-manage",
            capability_pack_id="unknown.pack.v1",
        )
        is False
    )
