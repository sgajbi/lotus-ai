from __future__ import annotations

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueBackoffStrategy,
    WorkflowPackQueueCancellationActor,
    WorkflowPackQueueCancellationPolicyDescriptor,
    WorkflowPackQueueDegradedReadinessBehavior,
    WorkflowPackQueueEvidenceRequirementDescriptor,
    WorkflowPackQueueLane,
    WorkflowPackQueueOperatorVisibility,
    WorkflowPackQueuePolicyDescriptor,
    WorkflowPackQueueRetryPolicyDescriptor,
    WorkflowPackQueueState,
)
from app.services.workflow_pack_phase1_specs import (
    ADVISOR_BRIEF_V1_SPEC,
    TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC,
    WORKSPACE_RATIONALE_V1_SPEC,
    WorkflowPackPhase1VersionSpec,
)


def list_workflow_pack_queue_policy_descriptors() -> list[WorkflowPackQueuePolicyDescriptor]:
    policies = [
        _latency_sensitive_advisor_brief_policy(),
        _review_support_workspace_rationale_policy(),
        _batch_twr_inspection_support_brief_policy(),
    ]
    _validate_queue_policy_identity(policies)
    return [policy.model_copy(deep=True) for policy in policies]


def get_workflow_pack_queue_policy_descriptor(
    *,
    pack_id: str,
    version: str,
) -> WorkflowPackQueuePolicyDescriptor | None:
    return next(
        (
            policy
            for policy in list_workflow_pack_queue_policy_descriptors()
            if policy.workflow_pack_id == pack_id and policy.workflow_pack_version == version
        ),
        None,
    )


def validate_workflow_pack_queue_policies() -> None:
    from app.services.workflow_pack_bindings import list_workflow_pack_execution_binding_descriptors

    policies_by_ref = {
        _policy_ref(policy): policy for policy in list_workflow_pack_queue_policy_descriptors()
    }
    binding_refs = {
        f"{binding.pack_id}@{binding.version}"
        for binding in list_workflow_pack_execution_binding_descriptors()
    }
    missing_policy_refs = sorted(binding_refs.difference(policies_by_ref))
    if missing_policy_refs:
        raise ValueError(
            "Executable workflow-pack versions missing queue policy: "
            + ", ".join(missing_policy_refs)
        )
    orphan_policy_refs = sorted(set(policies_by_ref).difference(binding_refs))
    if orphan_policy_refs:
        raise ValueError(
            "Queue policies must reference executable workflow-pack versions only: "
            + ", ".join(orphan_policy_refs)
        )


def _latency_sensitive_advisor_brief_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=ADVISOR_BRIEF_V1_SPEC,
        policy_id="queue-policy.advisor-brief.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.LATENCY_SENSITIVE,
            WorkflowPackQueueLane.REVIEW_SUPPORT,
        ],
        default_lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
        max_concurrent_runs_per_pack=4,
        max_concurrent_runs_per_lane=2,
        max_queued_runs_per_pack=40,
        max_queued_runs_per_lane=20,
        admission_timeout_seconds=15,
        execution_timeout_seconds=240,
        stale_queue_threshold_seconds=60,
        status_summary=[
            "Advisor-brief work defaults to the latency-sensitive lane so banker-facing generation cannot be starved by batch work.",
            "Review-support capacity is reserved for revision and supersession follow-up work without changing review-state authority.",
        ],
    )


def _review_support_workspace_rationale_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=WORKSPACE_RATIONALE_V1_SPEC,
        policy_id="queue-policy.workspace-rationale.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.BATCH,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=30,
        max_queued_runs_per_lane=15,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "Workspace rationale work defaults to review-support capacity because the owning advisory workflow remains consequence-bearing.",
            "Batch capacity is allowed for future bounded advisory workspace sweeps without changing lotus-advise workflow authority.",
        ],
    )


def _batch_twr_inspection_support_brief_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC,
        policy_id="queue-policy.twr-inspection-support-brief.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.BATCH,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.BATCH,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=30,
        execution_timeout_seconds=420,
        stale_queue_threshold_seconds=120,
        status_summary=[
            "TWR inspection support briefs default to batch capacity because the inspection artifact path is supportability-oriented.",
            "Operator capacity is reserved for controlled diagnosis and replay posture without exposing raw queue internals.",
        ],
    )


def _build_queue_policy(
    *,
    spec: WorkflowPackPhase1VersionSpec,
    policy_id: str,
    allowed_lanes: list[WorkflowPackQueueLane],
    default_lane: WorkflowPackQueueLane,
    max_concurrent_runs_per_pack: int,
    max_concurrent_runs_per_lane: int,
    max_queued_runs_per_pack: int,
    max_queued_runs_per_lane: int,
    admission_timeout_seconds: int,
    execution_timeout_seconds: int,
    stale_queue_threshold_seconds: int,
    status_summary: list[str],
) -> WorkflowPackQueuePolicyDescriptor:
    return WorkflowPackQueuePolicyDescriptor(
        policy_id=policy_id,
        workflow_pack_id=spec.pack_id,
        workflow_pack_version=spec.version,
        allowed_lanes=allowed_lanes,
        default_lane=default_lane,
        max_concurrent_runs_per_pack=max_concurrent_runs_per_pack,
        max_concurrent_runs_per_lane=max_concurrent_runs_per_lane,
        max_queued_runs_per_pack=max_queued_runs_per_pack,
        max_queued_runs_per_lane=max_queued_runs_per_lane,
        admission_timeout_seconds=admission_timeout_seconds,
        execution_timeout_seconds=execution_timeout_seconds,
        retry_policy=WorkflowPackQueueRetryPolicyDescriptor(
            max_attempts=2,
            backoff_strategy=WorkflowPackQueueBackoffStrategy.EXPONENTIAL,
            retryable_failure_codes=[
                "TRANSIENT_PROVIDER_FAILURE",
                "WORKER_LEASE_EXPIRED",
            ],
            non_retryable_failure_codes=[
                "CALLER_NOT_AUTHORIZED",
                "REGISTRY_NOT_READY",
                "RUN_LEDGER_NOT_READY",
                "TASK_FLOW_STORE_NOT_READY",
                "QUEUE_POLICY_NOT_FOUND",
            ],
        ),
        cancellation_policy=WorkflowPackQueueCancellationPolicyDescriptor(
            cancellable_by=[
                WorkflowPackQueueCancellationActor.CALLER,
                WorkflowPackQueueCancellationActor.OPERATOR,
                WorkflowPackQueueCancellationActor.PLATFORM_AUTOMATION,
            ],
            terminal_state=WorkflowPackQueueState.CANCELLED,
            evidence_required=True,
        ),
        stale_queue_threshold_seconds=stale_queue_threshold_seconds,
        saturation_attention_threshold=0.8,
        degraded_readiness_behavior=WorkflowPackQueueDegradedReadinessBehavior.REJECT,
        operator_visibility=WorkflowPackQueueOperatorVisibility.BOUNDED,
        evidence_requirements=[
            WorkflowPackQueueEvidenceRequirementDescriptor(
                evidence_type="registry_authorization",
                description="Registry activation, caller authorization, rollout, and workflow-surface posture.",
            ),
            WorkflowPackQueueEvidenceRequirementDescriptor(
                evidence_type="queue_policy_evaluation",
                description="Resolved queue policy id, pack version, default lane, and requested lane.",
            ),
            WorkflowPackQueueEvidenceRequirementDescriptor(
                evidence_type="capacity_evaluation",
                description="Per-pack and per-lane concurrency and queue-capacity posture.",
            ),
        ],
        status_summary=status_summary,
    )


def _validate_queue_policy_identity(policies: list[WorkflowPackQueuePolicyDescriptor]) -> None:
    seen_policy_ids: set[str] = set()
    seen_pack_refs: set[str] = set()
    for policy in policies:
        if policy.policy_id in seen_policy_ids:
            raise ValueError(f"Duplicate workflow-pack queue policy id: {policy.policy_id}")
        seen_policy_ids.add(policy.policy_id)
        policy_ref = _policy_ref(policy)
        if policy_ref in seen_pack_refs:
            raise ValueError(f"Duplicate workflow-pack queue policy ref: {policy_ref}")
        seen_pack_refs.add(policy_ref)


def _policy_ref(policy: WorkflowPackQueuePolicyDescriptor) -> str:
    return f"{policy.workflow_pack_id}@{policy.workflow_pack_version}"
