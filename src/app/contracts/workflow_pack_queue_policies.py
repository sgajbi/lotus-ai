from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class WorkflowPackQueueLane(str, Enum):
    LATENCY_SENSITIVE = "LATENCY_SENSITIVE"
    REVIEW_SUPPORT = "REVIEW_SUPPORT"
    BATCH = "BATCH"
    NIGHTLY = "NIGHTLY"
    OPERATOR = "OPERATOR"


class WorkflowPackQueueState(str, Enum):
    NOT_ADMITTED = "NOT_ADMITTED"
    QUEUED = "QUEUED"
    ADMITTED = "ADMITTED"
    RUNNING = "RUNNING"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    DEGRADED = "DEGRADED"
    COMPLETED_HANDOFF = "COMPLETED_HANDOFF"


TERMINAL_WORKFLOW_PACK_QUEUE_STATES = frozenset(
    {
        WorkflowPackQueueState.REJECTED,
        WorkflowPackQueueState.CANCELLED,
        WorkflowPackQueueState.TIMED_OUT,
        WorkflowPackQueueState.DEGRADED,
        WorkflowPackQueueState.COMPLETED_HANDOFF,
    }
)

WORKFLOW_PACK_QUEUE_STATE_TRANSITIONS: dict[
    WorkflowPackQueueState, frozenset[WorkflowPackQueueState]
] = {
    WorkflowPackQueueState.NOT_ADMITTED: frozenset(
        {
            WorkflowPackQueueState.QUEUED,
            WorkflowPackQueueState.REJECTED,
            WorkflowPackQueueState.DEGRADED,
        }
    ),
    WorkflowPackQueueState.QUEUED: frozenset(
        {
            WorkflowPackQueueState.ADMITTED,
            WorkflowPackQueueState.CANCELLED,
            WorkflowPackQueueState.TIMED_OUT,
            WorkflowPackQueueState.DEGRADED,
        }
    ),
    WorkflowPackQueueState.ADMITTED: frozenset(
        {
            WorkflowPackQueueState.RUNNING,
            WorkflowPackQueueState.CANCELLED,
            WorkflowPackQueueState.TIMED_OUT,
            WorkflowPackQueueState.DEGRADED,
        }
    ),
    WorkflowPackQueueState.RUNNING: frozenset(
        {
            WorkflowPackQueueState.CANCELLED,
            WorkflowPackQueueState.TIMED_OUT,
            WorkflowPackQueueState.DEGRADED,
            WorkflowPackQueueState.COMPLETED_HANDOFF,
        }
    ),
    WorkflowPackQueueState.REJECTED: frozenset(),
    WorkflowPackQueueState.CANCELLED: frozenset(),
    WorkflowPackQueueState.TIMED_OUT: frozenset(),
    WorkflowPackQueueState.DEGRADED: frozenset(),
    WorkflowPackQueueState.COMPLETED_HANDOFF: frozenset(),
}


def is_workflow_pack_queue_state_transition_allowed(
    *,
    current_state: WorkflowPackQueueState,
    next_state: WorkflowPackQueueState,
) -> bool:
    return next_state in WORKFLOW_PACK_QUEUE_STATE_TRANSITIONS[current_state]


class WorkflowPackQueueBackoffStrategy(str, Enum):
    NONE = "NONE"
    FIXED = "FIXED"
    EXPONENTIAL = "EXPONENTIAL"


class WorkflowPackQueueCancellationActor(str, Enum):
    CALLER = "CALLER"
    OPERATOR = "OPERATOR"
    PLATFORM_AUTOMATION = "PLATFORM_AUTOMATION"


class WorkflowPackQueueDegradedReadinessBehavior(str, Enum):
    REJECT = "REJECT"
    DEGRADED = "DEGRADED"


class WorkflowPackQueueOperatorVisibility(str, Enum):
    BOUNDED = "BOUNDED"
    INTERNAL_ONLY = "INTERNAL_ONLY"


class WorkflowPackQueueRetryPolicyDescriptor(BaseModel):
    max_attempts: int = Field(
        ge=1,
        le=3,
        description="Maximum queue-admission or execution-handoff attempts before terminal posture.",
    )
    backoff_strategy: WorkflowPackQueueBackoffStrategy = Field(
        description="Governed retry backoff strategy for retryable queue failures."
    )
    retryable_failure_codes: list[str] = Field(
        default_factory=list,
        description="Bounded failure codes that may be retried under this policy.",
    )
    non_retryable_failure_codes: list[str] = Field(
        min_length=1,
        description="Failure codes that must not be retried.",
    )

    @model_validator(mode="after")
    def _retry_policy_must_be_bounded(self) -> "WorkflowPackQueueRetryPolicyDescriptor":
        retryable_codes = set(self.retryable_failure_codes)
        non_retryable_codes = set(self.non_retryable_failure_codes)
        overlapping_codes = sorted(retryable_codes.intersection(non_retryable_codes))
        if overlapping_codes:
            raise ValueError(
                "retryable_failure_codes must not overlap non_retryable_failure_codes: "
                + ", ".join(overlapping_codes)
            )
        if self.max_attempts == 1 and self.backoff_strategy is not WorkflowPackQueueBackoffStrategy.NONE:
            raise ValueError("single-attempt queue policies must use NONE backoff")
        if self.max_attempts > 1 and self.backoff_strategy is WorkflowPackQueueBackoffStrategy.NONE:
            raise ValueError("multi-attempt queue policies require an explicit backoff strategy")
        return self


class WorkflowPackQueueCancellationPolicyDescriptor(BaseModel):
    cancellable_by: list[WorkflowPackQueueCancellationActor] = Field(
        min_length=1,
        description="Actor classes allowed to cancel queued or admitted work.",
    )
    terminal_state: WorkflowPackQueueState = Field(
        description="Terminal queue state emitted after successful cancellation."
    )
    evidence_required: bool = Field(
        description="Whether cancellation requires operator or caller evidence."
    )

    @model_validator(mode="after")
    def _cancellation_terminal_state_must_be_cancelled(
        self,
    ) -> "WorkflowPackQueueCancellationPolicyDescriptor":
        if self.terminal_state is not WorkflowPackQueueState.CANCELLED:
            raise ValueError("cancellation terminal_state must be CANCELLED")
        if not self.evidence_required:
            raise ValueError("queue cancellation policy must require evidence")
        return self


class WorkflowPackQueueEvidenceRequirementDescriptor(BaseModel):
    evidence_type: str = Field(
        min_length=1,
        description="Stable evidence type required to prove queue-policy evaluation.",
    )
    description: str = Field(
        min_length=1,
        description="Human-readable explanation of the evidence requirement.",
    )


class WorkflowPackQueuePolicyDescriptor(BaseModel):
    policy_id: str = Field(
        min_length=1,
        description="Stable queue policy identifier for one workflow-pack version.",
    )
    workflow_pack_id: str = Field(
        min_length=1,
        description="Workflow-pack family identifier governed by this queue policy.",
    )
    workflow_pack_version: str = Field(
        min_length=1,
        description="Workflow-pack version governed by this queue policy.",
    )
    allowed_lanes: list[WorkflowPackQueueLane] = Field(
        min_length=1,
        description="Finite queue lanes this workflow-pack version may use.",
    )
    default_lane: WorkflowPackQueueLane = Field(
        description="Default queue lane when the request omits an explicit lane."
    )
    max_concurrent_runs_per_pack: int = Field(
        ge=1,
        le=25,
        description="Maximum concurrently admitted runs for this workflow-pack version.",
    )
    max_concurrent_runs_per_lane: int = Field(
        ge=1,
        le=25,
        description="Maximum concurrently admitted runs for this workflow-pack version in one lane.",
    )
    max_queued_runs_per_pack: int = Field(
        ge=1,
        le=500,
        description="Maximum queued runs for this workflow-pack version before rejection.",
    )
    max_queued_runs_per_lane: int = Field(
        ge=1,
        le=500,
        description="Maximum queued runs for this workflow-pack version in one lane before rejection.",
    )
    admission_timeout_seconds: int = Field(
        ge=1,
        le=600,
        description="Maximum time a request may spend at the queue admission boundary.",
    )
    execution_timeout_seconds: int = Field(
        ge=1,
        le=14400,
        description="Maximum time admitted execution may run before timeout posture.",
    )
    retry_policy: WorkflowPackQueueRetryPolicyDescriptor = Field(
        description="Bounded retry policy for queue and handoff failures."
    )
    cancellation_policy: WorkflowPackQueueCancellationPolicyDescriptor = Field(
        description="Bounded cancellation policy for queued or admitted work."
    )
    stale_queue_threshold_seconds: int = Field(
        ge=1,
        le=86400,
        description="Age threshold after which queued work becomes stale for operator posture.",
    )
    saturation_attention_threshold: float = Field(
        gt=0,
        le=1,
        description="Queue utilization ratio that should produce operator attention.",
    )
    degraded_readiness_behavior: WorkflowPackQueueDegradedReadinessBehavior = Field(
        description="Terminal posture when registry, run-ledger, task-flow, or queue source truth is not ready."
    )
    operator_visibility: WorkflowPackQueueOperatorVisibility = Field(
        description="Bounded operator visibility posture for this policy."
    )
    evidence_requirements: list[WorkflowPackQueueEvidenceRequirementDescriptor] = Field(
        min_length=1,
        description="Evidence requirements that must be satisfied when queue policy is evaluated.",
    )
    status_summary: list[str] = Field(
        min_length=1,
        description="Human-readable summary of the queue policy posture.",
    )

    @model_validator(mode="after")
    def _queue_policy_must_be_bounded(self) -> "WorkflowPackQueuePolicyDescriptor":
        allowed_lanes = set(self.allowed_lanes)
        if self.default_lane not in allowed_lanes:
            raise ValueError("default_lane must be included in allowed_lanes")
        if self.max_concurrent_runs_per_lane > self.max_concurrent_runs_per_pack:
            raise ValueError(
                "max_concurrent_runs_per_lane must not exceed max_concurrent_runs_per_pack"
            )
        if self.max_queued_runs_per_lane > self.max_queued_runs_per_pack:
            raise ValueError("max_queued_runs_per_lane must not exceed max_queued_runs_per_pack")
        if self.execution_timeout_seconds <= self.admission_timeout_seconds:
            raise ValueError("execution_timeout_seconds must exceed admission_timeout_seconds")
        if self.stale_queue_threshold_seconds <= self.admission_timeout_seconds:
            raise ValueError("stale_queue_threshold_seconds must exceed admission_timeout_seconds")
        evidence_types = {
            requirement.evidence_type for requirement in self.evidence_requirements
        }
        required_evidence_types = {
            "registry_authorization",
            "queue_policy_evaluation",
            "capacity_evaluation",
        }
        missing_evidence_types = sorted(required_evidence_types.difference(evidence_types))
        if missing_evidence_types:
            raise ValueError(
                "queue policy missing required evidence types: "
                + ", ".join(missing_evidence_types)
            )
        return self
