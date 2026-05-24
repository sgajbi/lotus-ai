from pytest import MonkeyPatch

from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueLane
from app.services import workflow_pack_queue_policy_catalog
from app.services.workflow_pack_queue_policy_catalog import (
    _validate_queue_policy_identity,
    get_workflow_pack_queue_policy_descriptor,
    list_workflow_pack_queue_policy_descriptors,
    validate_workflow_pack_queue_policies,
)


def test_queue_policy_catalog_declares_policy_for_each_executable_phase1_pack() -> None:
    policies = list_workflow_pack_queue_policy_descriptors()

    policy_refs = {
        f"{policy.workflow_pack_id}@{policy.workflow_pack_version}" for policy in policies
    }
    assert policy_refs == {
        "advisor_brief.pack@v1",
        "dpm_exception_summary.pack@v1",
        "dpm_operations_handoff_summary.pack@v1",
        "dpm_pm_memo.pack@v1",
        "dpm_wave_pm_memo.pack@v1",
        "outcome_review_narrative.pack@v1",
        "pm_quality_summary.pack@v1",
        "proposal_memo_commentary.pack@v1",
        "workspace_rationale.pack@v1",
        "twr_inspection_support_brief.pack@v1",
    }
    assert len({policy.policy_id for policy in policies}) == len(policies)
    validate_workflow_pack_queue_policies()


def test_queue_policy_catalog_keeps_discovery_only_versions_without_policy() -> None:
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id="advisor_brief.pack",
        version="v2",
    )

    assert policy is None


def test_advisor_brief_queue_policy_protects_latency_sensitive_lane() -> None:
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert policy is not None
    assert policy.default_lane == WorkflowPackQueueLane.LATENCY_SENSITIVE
    assert policy.allowed_lanes == [
        WorkflowPackQueueLane.LATENCY_SENSITIVE,
        WorkflowPackQueueLane.REVIEW_SUPPORT,
    ]
    assert policy.max_concurrent_runs_per_pack == 4
    assert policy.max_concurrent_runs_per_lane == 2
    assert policy.max_queued_runs_per_pack == 40
    assert policy.max_queued_runs_per_lane == 20
    assert any(
        requirement.evidence_type == "capacity_evaluation"
        for requirement in policy.evidence_requirements
    )


def test_queue_policy_catalog_returns_deep_copies() -> None:
    policies = list_workflow_pack_queue_policy_descriptors()
    policies[0].status_summary.append("mutated by test")

    fresh_policy = get_workflow_pack_queue_policy_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert fresh_policy is not None
    assert "mutated by test" not in fresh_policy.status_summary


def test_queue_policy_validation_rejects_executable_binding_without_policy(
    monkeypatch: MonkeyPatch,
) -> None:
    policies = [
        policy
        for policy in list_workflow_pack_queue_policy_descriptors()
        if policy.workflow_pack_id != "advisor_brief.pack"
    ]
    monkeypatch.setattr(
        workflow_pack_queue_policy_catalog,
        "list_workflow_pack_queue_policy_descriptors",
        lambda: policies,
    )

    try:
        validate_workflow_pack_queue_policies()
    except ValueError as exc:
        assert "Executable workflow-pack versions missing queue policy" in str(exc)
        assert "advisor_brief.pack@v1" in str(exc)
    else:
        raise AssertionError("Expected missing queue policy for executable pack to fail")


def test_queue_policy_validation_rejects_policy_without_executable_binding(
    monkeypatch: MonkeyPatch,
) -> None:
    policies = list_workflow_pack_queue_policy_descriptors()
    orphan = policies[0].model_copy(update={"workflow_pack_version": "v9"})
    monkeypatch.setattr(
        workflow_pack_queue_policy_catalog,
        "list_workflow_pack_queue_policy_descriptors",
        lambda: [*policies, orphan],
    )

    try:
        validate_workflow_pack_queue_policies()
    except ValueError as exc:
        assert "Queue policies must reference executable workflow-pack versions only" in str(exc)
        assert "advisor_brief.pack@v9" in str(exc)
    else:
        raise AssertionError("Expected orphan queue policy to fail")


def test_queue_policy_identity_validation_rejects_duplicate_policy_ids_and_refs() -> None:
    policies = list_workflow_pack_queue_policy_descriptors()
    duplicate_id = policies[1].model_copy(update={"policy_id": policies[0].policy_id})

    try:
        _validate_queue_policy_identity([policies[0], duplicate_id])
    except ValueError as exc:
        assert "Duplicate workflow-pack queue policy id" in str(exc)
    else:
        raise AssertionError("expected duplicate queue policy id to fail")

    duplicate_ref = policies[1].model_copy(
        update={
            "workflow_pack_id": policies[0].workflow_pack_id,
            "workflow_pack_version": policies[0].workflow_pack_version,
        }
    )
    try:
        _validate_queue_policy_identity([policies[0], duplicate_ref])
    except ValueError as exc:
        assert "Duplicate workflow-pack queue policy ref" in str(exc)
    else:
        raise AssertionError("expected duplicate queue policy ref to fail")
