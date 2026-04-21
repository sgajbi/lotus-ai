from pydantic import ValidationError

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
    TERMINAL_WORKFLOW_PACK_QUEUE_STATES,
    is_workflow_pack_queue_state_transition_allowed,
)


def _valid_policy(**overrides: object) -> WorkflowPackQueuePolicyDescriptor:
    payload = {
        "policy_id": "queue-policy.advisor_brief.v1",
        "workflow_pack_id": "advisor_brief.pack",
        "workflow_pack_version": "v1",
        "allowed_lanes": [
            WorkflowPackQueueLane.LATENCY_SENSITIVE,
            WorkflowPackQueueLane.REVIEW_SUPPORT,
        ],
        "default_lane": WorkflowPackQueueLane.LATENCY_SENSITIVE,
        "max_concurrent_runs_per_pack": 4,
        "max_concurrent_runs_per_lane": 2,
        "max_queued_runs_per_pack": 40,
        "max_queued_runs_per_lane": 20,
        "admission_timeout_seconds": 15,
        "execution_timeout_seconds": 240,
        "retry_policy": WorkflowPackQueueRetryPolicyDescriptor(
            max_attempts=2,
            backoff_strategy=WorkflowPackQueueBackoffStrategy.EXPONENTIAL,
            retryable_failure_codes=["TRANSIENT_PROVIDER_FAILURE"],
            non_retryable_failure_codes=[
                "CALLER_NOT_AUTHORIZED",
                "REGISTRY_NOT_READY",
                "RUN_LEDGER_NOT_READY",
            ],
        ),
        "cancellation_policy": WorkflowPackQueueCancellationPolicyDescriptor(
            cancellable_by=[
                WorkflowPackQueueCancellationActor.CALLER,
                WorkflowPackQueueCancellationActor.OPERATOR,
            ],
            terminal_state=WorkflowPackQueueState.CANCELLED,
            evidence_required=True,
        ),
        "stale_queue_threshold_seconds": 60,
        "saturation_attention_threshold": 0.8,
        "degraded_readiness_behavior": WorkflowPackQueueDegradedReadinessBehavior.REJECT,
        "operator_visibility": WorkflowPackQueueOperatorVisibility.BOUNDED,
        "evidence_requirements": [
            WorkflowPackQueueEvidenceRequirementDescriptor(
                evidence_type="registry_authorization",
                description="Registry activation, caller, rollout, and scope posture.",
            ),
            WorkflowPackQueueEvidenceRequirementDescriptor(
                evidence_type="queue_policy_evaluation",
                description="Resolved queue policy id and requested lane.",
            ),
            WorkflowPackQueueEvidenceRequirementDescriptor(
                evidence_type="capacity_evaluation",
                description="Per-pack and per-lane capacity posture at admission time.",
            ),
        ],
        "status_summary": [
            "Advisor-brief queue policy protects latency-sensitive work while preserving review-support capacity."
        ],
    }
    payload.update(overrides)
    return WorkflowPackQueuePolicyDescriptor.model_validate(payload)


def test_workflow_pack_queue_policy_accepts_bounded_latency_sensitive_policy() -> None:
    policy = _valid_policy()

    assert policy.policy_id == "queue-policy.advisor_brief.v1"
    assert policy.default_lane == WorkflowPackQueueLane.LATENCY_SENSITIVE
    assert policy.max_concurrent_runs_per_pack == 4
    assert policy.max_concurrent_runs_per_lane == 2
    assert policy.retry_policy.max_attempts == 2
    assert policy.cancellation_policy.terminal_state == WorkflowPackQueueState.CANCELLED


def test_workflow_pack_queue_state_model_blocks_terminal_requeue() -> None:
    assert is_workflow_pack_queue_state_transition_allowed(
        current_state=WorkflowPackQueueState.NOT_ADMITTED,
        next_state=WorkflowPackQueueState.QUEUED,
    )
    assert is_workflow_pack_queue_state_transition_allowed(
        current_state=WorkflowPackQueueState.QUEUED,
        next_state=WorkflowPackQueueState.ADMITTED,
    )
    assert is_workflow_pack_queue_state_transition_allowed(
        current_state=WorkflowPackQueueState.RUNNING,
        next_state=WorkflowPackQueueState.COMPLETED_HANDOFF,
    )

    for terminal_state in TERMINAL_WORKFLOW_PACK_QUEUE_STATES:
        assert not is_workflow_pack_queue_state_transition_allowed(
            current_state=terminal_state,
            next_state=WorkflowPackQueueState.QUEUED,
        )


def test_workflow_pack_queue_policy_rejects_default_lane_outside_allowed_lanes() -> None:
    try:
        _valid_policy(default_lane=WorkflowPackQueueLane.BATCH)
    except ValidationError as exc:
        assert "default_lane must be included in allowed_lanes" in str(exc)
    else:
        raise AssertionError("Expected queue policy with unsupported default lane to fail")


def test_workflow_pack_queue_policy_rejects_unbounded_or_impossible_capacity() -> None:
    try:
        _valid_policy(max_concurrent_runs_per_pack=0)
    except ValidationError as exc:
        assert "greater than or equal to 1" in str(exc)
    else:
        raise AssertionError("Expected zero max_concurrent_runs_per_pack to fail")

    try:
        _valid_policy(max_concurrent_runs_per_pack=2, max_concurrent_runs_per_lane=3)
    except ValidationError as exc:
        assert "max_concurrent_runs_per_lane must not exceed" in str(exc)
    else:
        raise AssertionError("Expected lane concurrency above pack concurrency to fail")


def test_workflow_pack_queue_policy_rejects_invalid_timeout_ordering() -> None:
    try:
        _valid_policy(admission_timeout_seconds=240, execution_timeout_seconds=240)
    except ValidationError as exc:
        assert "execution_timeout_seconds must exceed admission_timeout_seconds" in str(exc)
    else:
        raise AssertionError("Expected execution timeout equal to admission timeout to fail")

    try:
        _valid_policy(admission_timeout_seconds=90, stale_queue_threshold_seconds=60)
    except ValidationError as exc:
        assert "stale_queue_threshold_seconds must exceed admission_timeout_seconds" in str(exc)
    else:
        raise AssertionError("Expected stale threshold below admission timeout to fail")


def test_workflow_pack_queue_retry_policy_blocks_retry_amplification() -> None:
    try:
        WorkflowPackQueueRetryPolicyDescriptor(
            max_attempts=2,
            backoff_strategy=WorkflowPackQueueBackoffStrategy.NONE,
            retryable_failure_codes=["PROVIDER_TIMEOUT"],
            non_retryable_failure_codes=["CALLER_NOT_AUTHORIZED"],
        )
    except ValidationError as exc:
        assert "multi-attempt queue policies require an explicit backoff strategy" in str(exc)
    else:
        raise AssertionError("Expected multi-attempt retry policy without backoff to fail")

    try:
        WorkflowPackQueueRetryPolicyDescriptor(
            max_attempts=2,
            backoff_strategy=WorkflowPackQueueBackoffStrategy.FIXED,
            retryable_failure_codes=["REGISTRY_NOT_READY"],
            non_retryable_failure_codes=["REGISTRY_NOT_READY"],
        )
    except ValidationError as exc:
        assert "must not overlap" in str(exc)
    else:
        raise AssertionError("Expected overlapping retryable/non-retryable codes to fail")


def test_workflow_pack_queue_cancellation_requires_cancelled_terminal_evidence() -> None:
    try:
        WorkflowPackQueueCancellationPolicyDescriptor(
            cancellable_by=[WorkflowPackQueueCancellationActor.OPERATOR],
            terminal_state=WorkflowPackQueueState.REJECTED,
            evidence_required=True,
        )
    except ValidationError as exc:
        assert "terminal_state must be CANCELLED" in str(exc)
    else:
        raise AssertionError("Expected non-cancelled terminal cancellation state to fail")

    try:
        WorkflowPackQueueCancellationPolicyDescriptor(
            cancellable_by=[WorkflowPackQueueCancellationActor.OPERATOR],
            terminal_state=WorkflowPackQueueState.CANCELLED,
            evidence_required=False,
        )
    except ValidationError as exc:
        assert "must require evidence" in str(exc)
    else:
        raise AssertionError("Expected cancellation without evidence to fail")


def test_workflow_pack_queue_policy_requires_admission_evidence_types() -> None:
    try:
        _valid_policy(
            evidence_requirements=[
                WorkflowPackQueueEvidenceRequirementDescriptor(
                    evidence_type="registry_authorization",
                    description="Registry activation and caller posture.",
                )
            ]
        )
    except ValidationError as exc:
        assert "queue policy missing required evidence types" in str(exc)
        assert "capacity_evaluation" in str(exc)
        assert "queue_policy_evaluation" in str(exc)
    else:
        raise AssertionError("Expected queue policy with missing evidence requirements to fail")
