from __future__ import annotations

from typing import TYPE_CHECKING

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueBackoffStrategy,
    WorkflowPackQueueCancellationActor,
    WorkflowPackQueueCancellationPolicyDescriptor,
    WorkflowPackQueueDegradedReadinessBehavior,
    WorkflowPackQueueEvidenceRequirementDescriptor,
    WorkflowPackQueueLane,
    WorkflowPackQueueLaneStatusDescriptor,
    WorkflowPackQueueOperatorVisibility,
    WorkflowPackQueuePolicyCatalogResponse,
    WorkflowPackQueuePolicyDescriptor,
    WorkflowPackQueuePolicyDetailResponse,
    WorkflowPackQueueRetryPolicyDescriptor,
    WorkflowPackQueueSaturationStatus,
    WorkflowPackQueueState,
    WorkflowPackQueueStatusDetailResponse,
    WorkflowPackQueueStatusItemDescriptor,
    WorkflowPackQueueStatusResponse,
)
from app.config import settings
from app.services.workflow_pack_phase1_specs import (
    ADVISOR_BRIEF_V1_SPEC,
    ADVISORY_COPILOT_ACTION_PACK_SPECS,
    DPM_EXCEPTION_SUMMARY_V1_SPEC,
    DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC,
    DPM_WAVE_PM_MEMO_V1_SPEC,
    OUTCOME_REVIEW_NARRATIVE_V1_SPEC,
    PM_QUALITY_SUMMARY_V1_SPEC,
    PROPOSAL_MEMO_COMMENTARY_V1_SPEC,
    PROOF_PACK_PM_MEMO_V1_SPEC,
    TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC,
    WORKSPACE_RATIONALE_V1_SPEC,
    WorkflowPackPhase1VersionSpec,
)

if TYPE_CHECKING:
    from app.services.workflow_pack_queue_admission import WorkflowPackQueueAdmissionLease


def list_workflow_pack_queue_policy_descriptors() -> list[WorkflowPackQueuePolicyDescriptor]:
    policies = [
        _latency_sensitive_advisor_brief_policy(),
        _review_support_workspace_rationale_policy(),
        _review_support_proposal_memo_commentary_policy(),
        *[
            _review_support_advisory_copilot_policy(spec=spec)
            for spec in ADVISORY_COPILOT_ACTION_PACK_SPECS
        ],
        _batch_twr_inspection_support_brief_policy(),
        _review_support_proof_pack_pm_memo_policy(),
        _review_support_outcome_review_narrative_policy(),
        _review_support_wave_pm_memo_policy(),
        _review_support_operations_handoff_summary_policy(),
        _review_support_dpm_exception_summary_policy(),
        _review_support_pm_quality_summary_policy(),
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


def build_workflow_pack_queue_policy_catalog() -> WorkflowPackQueuePolicyCatalogResponse:
    from app.services.workflow_pack_registry import list_workflow_pack_registrations

    list_workflow_pack_registrations()
    policies = list_workflow_pack_queue_policy_descriptors()
    return WorkflowPackQueuePolicyCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        policy_count=len(policies),
        policies=policies,
        status_summary=[
            "Workflow-pack queue policies are declared for executable pack versions only.",
            "Queue policy posture is source policy; queue-status endpoints expose current admission posture.",
        ],
    )


def build_workflow_pack_queue_policy_detail(
    *,
    pack_id: str,
    version: str,
) -> WorkflowPackQueuePolicyDetailResponse:
    from app.services.workflow_pack_registry import list_workflow_pack_registrations

    list_workflow_pack_registrations()
    policy = get_workflow_pack_queue_policy_descriptor(pack_id=pack_id, version=version)
    if policy is None:
        raise ValueError(f"Unknown workflow-pack queue policy: {pack_id}@{version}")
    return WorkflowPackQueuePolicyDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        policy=policy,
        status_summary=[
            "Queue policy detail is version-scoped and does not expose raw worker internals.",
            "Runtime queue admission remains separate from run-ledger and task-flow lifecycle state.",
        ],
    )


def build_workflow_pack_queue_status() -> WorkflowPackQueueStatusResponse:
    from app.services.workflow_pack_registry import list_workflow_pack_registrations
    from app.services.workflow_pack_queue_admission import (
        list_active_workflow_pack_queue_admissions,
    )

    list_workflow_pack_registrations()
    policies = list_workflow_pack_queue_policy_descriptors()
    active_leases = list_active_workflow_pack_queue_admissions()
    active_items = [_map_queue_status_item(lease) for lease in active_leases]
    lane_statuses = [
        _build_lane_status(policy=policy, lane=lane, active_leases=active_leases)
        for policy in policies
        for lane in policy.allowed_lanes
    ]
    return WorkflowPackQueueStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        queue_source_mode="memory",
        active_admission_count=len(active_items),
        lane_statuses=lane_statuses,
        active_items=active_items,
        status_summary=[
            "Workflow-pack queue status reports current in-process admission leases only.",
            "Queue status does not replace workflow-pack run, review, or task-flow lifecycle state.",
        ],
    )


def build_workflow_pack_queue_status_detail(
    *,
    queue_item_id: str,
) -> WorkflowPackQueueStatusDetailResponse:
    from app.services.workflow_pack_registry import list_workflow_pack_registrations
    from app.services.workflow_pack_queue_admission import (
        get_active_workflow_pack_queue_admission,
    )

    list_workflow_pack_registrations()
    lease = get_active_workflow_pack_queue_admission(queue_item_id)
    if lease is None:
        raise ValueError(f"Unknown active workflow-pack queue item: {queue_item_id}")
    return WorkflowPackQueueStatusDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        queue_item=_map_queue_status_item(lease),
        status_summary=[
            "Queue item detail is bounded to source admission posture and hides raw worker internals."
        ],
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


def _review_support_proposal_memo_commentary_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=PROPOSAL_MEMO_COMMENTARY_V1_SPEC,
        policy_id="queue-policy.proposal-memo-commentary.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
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
            "Proposal memo commentary defaults to review-support capacity because generated language remains advisor-use and review-gated.",
            "Operator capacity is reserved for controlled investigation of unavailable, guardrail-blocked, or stale memo-commentary runs.",
        ],
    )


def _review_support_advisory_copilot_policy(
    *, spec: WorkflowPackPhase1VersionSpec
) -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=spec,
        policy_id=f"queue-policy.{spec.pack_family.replace('_', '-')}.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
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
            "Advisory copilot work defaults to review-support capacity because generated content is evidence-backed and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, disabled-pack, or stale copilot posture.",
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


def _review_support_outcome_review_narrative_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=OUTCOME_REVIEW_NARRATIVE_V1_SPEC,
        policy_id="queue-policy.outcome-review-narrative.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "Outcome-review narrative work defaults to review-support capacity because generated text remains support-only and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, or stale outcome-evidence posture.",
        ],
    )


def _review_support_proof_pack_pm_memo_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=PROOF_PACK_PM_MEMO_V1_SPEC,
        policy_id="queue-policy.dpm-pm-memo.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "DPM PM memo work defaults to review-support capacity because generated narrative remains support-only and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, or stale proof-pack evidence posture.",
        ],
    )


def _review_support_wave_pm_memo_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=DPM_WAVE_PM_MEMO_V1_SPEC,
        policy_id="queue-policy.dpm-wave-pm-memo.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "DPM wave PM memo work defaults to review-support capacity because generated narrative remains support-only and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, or stale wave-evidence posture.",
        ],
    )


def _review_support_operations_handoff_summary_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC,
        policy_id="queue-policy.dpm-operations-handoff-summary.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "DPM operations handoff summaries default to review-support capacity because generated text remains support-only and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, or stale handoff-evidence posture.",
        ],
    )


def _review_support_dpm_exception_summary_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=DPM_EXCEPTION_SUMMARY_V1_SPEC,
        policy_id="queue-policy.dpm-exception-summary.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "DPM exception summaries default to review-support capacity because generated text remains support-only and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, or stale exception-evidence posture.",
        ],
    )


def _review_support_pm_quality_summary_policy() -> WorkflowPackQueuePolicyDescriptor:
    return _build_queue_policy(
        spec=PM_QUALITY_SUMMARY_V1_SPEC,
        policy_id="queue-policy.pm-quality-summary.v1",
        allowed_lanes=[
            WorkflowPackQueueLane.REVIEW_SUPPORT,
            WorkflowPackQueueLane.OPERATOR,
        ],
        default_lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
        max_concurrent_runs_per_pack=2,
        max_concurrent_runs_per_lane=1,
        max_queued_runs_per_pack=25,
        max_queued_runs_per_lane=10,
        admission_timeout_seconds=20,
        execution_timeout_seconds=300,
        stale_queue_threshold_seconds=90,
        status_summary=[
            "PM quality summaries default to review-support capacity because generated text remains support-only and review-gated.",
            "Operator capacity is reserved for controlled investigation of guardrail-blocked, unavailable, or stale PM-quality evidence posture.",
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
                "EXECUTION_TIMEOUT",
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


def _map_queue_status_item(
    lease: WorkflowPackQueueAdmissionLease,
) -> WorkflowPackQueueStatusItemDescriptor:
    return WorkflowPackQueueStatusItemDescriptor(
        queue_item_id=lease.queue_item_id,
        policy_id=lease.policy_id,
        workflow_pack_id=lease.workflow_pack_id,
        workflow_pack_version=lease.workflow_pack_version,
        lane=lease.lane,
        state=lease.state,
        admitted_at=lease.admitted_at,
    )


def _build_lane_status(
    *,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane,
    active_leases: list[WorkflowPackQueueAdmissionLease],
) -> WorkflowPackQueueLaneStatusDescriptor:
    active_count = sum(
        1
        for lease in active_leases
        if lease.workflow_pack_id == policy.workflow_pack_id
        and lease.workflow_pack_version == policy.workflow_pack_version
        and lease.lane == lane
    )
    saturation_ratio = active_count / policy.max_concurrent_runs_per_lane
    return WorkflowPackQueueLaneStatusDescriptor(
        policy_id=policy.policy_id,
        workflow_pack_id=policy.workflow_pack_id,
        workflow_pack_version=policy.workflow_pack_version,
        lane=lane,
        active_count=active_count,
        max_concurrent_runs_per_lane=policy.max_concurrent_runs_per_lane,
        max_queued_runs_per_lane=policy.max_queued_runs_per_lane,
        saturation_attention_threshold=policy.saturation_attention_threshold,
        saturation_status=(
            WorkflowPackQueueSaturationStatus.SATURATED
            if saturation_ratio >= policy.saturation_attention_threshold
            else WorkflowPackQueueSaturationStatus.HEALTHY
        ),
    )
