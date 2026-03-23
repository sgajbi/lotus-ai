from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvaluationAssetStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    STAGED = "STAGED"


class EvaluationRunStatus(str, Enum):
    RECORDED = "RECORDED"
    SUPERSEDED = "SUPERSEDED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class EvaluationRunRecordSource(str, Enum):
    STAGED_ARTIFACT = "STAGED_ARTIFACT"
    RUNTIME_STATE = "RUNTIME_STATE"


class EvaluationRunSubmissionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"


class EvaluationCaseOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class EvaluationRunVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class EvaluationApprovalEvidenceState(str, Enum):
    NO_EVIDENCE = "NO_EVIDENCE"
    STAGED_ONLY = "STAGED_ONLY"
    RUNTIME_IN_PROGRESS = "RUNTIME_IN_PROGRESS"
    RUNTIME_PARTIAL = "RUNTIME_PARTIAL"
    RUNTIME_PASS = "RUNTIME_PASS"
    RUNTIME_FAIL = "RUNTIME_FAIL"
    RUNTIME_STALE = "RUNTIME_STALE"


class EvaluationEvidenceCategoryDescriptor(BaseModel):
    category_id: str = Field(description="Stable execution evidence category identifier.")
    description: str = Field(description="Human-readable description of the evidence category.")


class EvaluationFixtureDescriptor(BaseModel):
    fixture_id: str = Field(description="Stable evaluation fixture family identifier.")
    status: EvaluationAssetStatus = Field(
        description="Current maturity status for the fixture family."
    )
    description: str = Field(description="Human-readable description of the fixture family.")
    manifest_path: str | None = Field(
        default=None,
        description="Repository-relative path to the backing fixture asset when one exists.",
    )
    case_count: int = Field(
        default=0,
        description="Number of concrete fixture cases currently staged for the family.",
    )


class EvaluationFixtureCaseDescriptor(BaseModel):
    case_id: str = Field(description="Stable evaluation case identifier within the fixture family.")
    summary: str = Field(description="Short human-readable summary of the evaluation case.")


class EvaluationFixtureDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation fixture detail.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    manifest_version: str = Field(
        description="Version identifier for the evaluation fixture manifest."
    )
    fixture: EvaluationFixtureDescriptor = Field(
        description="Governed descriptor for the requested evaluation fixture family."
    )
    task_id: str | None = Field(
        default=None,
        description="Bounded task identifier associated with the fixture family when available.",
    )
    cases: list[EvaluationFixtureCaseDescriptor] = Field(
        description="Case-level metadata for the fixture family without embedding raw prompt payloads."
    )


class EvaluationCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    manifest_version: str = Field(
        description="Version identifier for the evaluation fixture manifest."
    )
    evidence_categories: list[EvaluationEvidenceCategoryDescriptor] = Field(
        description="Execution evidence categories currently emitted by lotus-ai."
    )
    fixture_families: list[EvaluationFixtureDescriptor] = Field(
        description="Known evaluation fixture families for current and planned regression coverage."
    )


class EvaluationSeamCoverageDescriptor(BaseModel):
    seam_id: str = Field(
        description="Stable platform seam identifier represented in evaluation assets."
    )
    fixture_ids: list[str] = Field(description="Fixture families that currently cover the seam.")
    staged_fixture_count: int = Field(
        description="Number of staged fixture families currently mapped to the seam."
    )
    staged_case_count: int = Field(description="Total staged cases currently mapped to the seam.")


class EvaluationRunArtifactDescriptor(BaseModel):
    run_id: str = Field(description="Stable evaluation run artifact identifier.")
    recorded_at: str = Field(
        description="UTC timestamp when the evaluation run was recorded or submitted."
    )
    status: EvaluationRunStatus = Field(
        description="Lifecycle status for the exposed evaluation run."
    )
    record_source: EvaluationRunRecordSource = Field(
        default=EvaluationRunRecordSource.STAGED_ARTIFACT,
        description="Whether the run comes from historical staged artifacts or durable runtime state.",
    )
    manifest_version: str = Field(
        description="Evaluation fixture manifest version associated with the run."
    )
    fixture_id: str | None = Field(
        default=None,
        description="Fixture family identifier for runtime-backed evaluation runs when one exists.",
    )
    async_job_id: str | None = Field(
        default=None,
        description="Related async job identifier for runtime-backed evaluation runs when one exists.",
    )
    triggered_by: str | None = Field(
        default=None,
        description="Operator or system identity that triggered the runtime-backed evaluation run.",
    )
    staged_fixture_count: int = Field(
        description="Number of staged fixture families represented in the exposed run."
    )
    staged_case_count: int = Field(
        description="Number of staged cases represented in the exposed run."
    )
    seam_coverage: list[EvaluationSeamCoverageDescriptor] = Field(
        description="Seam-oriented coverage associated with the exposed evaluation run."
    )
    notes: str = Field(
        description="Human-readable description of the exposed evaluation run."
    )


class EvaluationRunCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation run catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    run_count: int = Field(description="Number of evaluation runs currently exposed.")
    latest_run_id: str | None = Field(
        default=None,
        description="Most recent evaluation run identifier when one exists.",
    )
    runtime_backed_run_count: int = Field(
        description="Number of durable runtime-backed evaluation runs currently exposed."
    )
    historical_run_count: int = Field(
        description="Number of historical staged-artifact evaluation runs currently exposed."
    )
    status_counts: dict[EvaluationRunStatus, int] = Field(
        description="Evaluation run counts by lifecycle status across runtime-backed and historical records."
    )
    runs: list[EvaluationRunArtifactDescriptor] = Field(
        description="Evaluation runs available for inspection."
    )


class EvaluationRunDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation run detail.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    run: EvaluationRunArtifactDescriptor = Field(
        description="Evaluation run detail from historical artifacts or durable runtime state."
    )
    attempts: list["EvaluationRunAttemptDescriptor"] = Field(
        default_factory=list,
        description="Persisted runtime-backed attempt history for the evaluation run.",
    )
    case_results: list["EvaluationCaseResultDescriptor"] = Field(
        default_factory=list,
        description="Persisted runtime-backed case outcomes for the evaluation run.",
    )


class EvaluationRunAttemptDescriptor(BaseModel):
    attempt_id: str = Field(description="Stable evaluation run attempt identifier.")
    attempt_number: int = Field(description="Monotonic attempt number for the evaluation run.")
    status: EvaluationRunStatus = Field(description="Lifecycle status for the recorded attempt.")
    started_at: str | None = Field(
        default=None,
        description="UTC timestamp when the attempt entered running execution.",
    )
    completed_at: str | None = Field(
        default=None,
        description="UTC timestamp when the attempt reached a terminal state.",
    )
    worker_id: str | None = Field(
        default=None,
        description="Worker identity that executed the attempt when one exists.",
    )
    message: str = Field(description="Human-readable attempt lifecycle message.")
    verdict: EvaluationRunVerdict | None = Field(
        default=None,
        description="Attempt-level verdict derived from persisted case outcomes.",
    )
    failure_reason: str | None = Field(
        default=None,
        description="Terminal failure reason when the attempt does not complete successfully.",
    )


class EvaluationCaseResultDescriptor(BaseModel):
    case_result_id: str = Field(description="Stable persisted evaluation case-result identifier.")
    attempt_id: str = Field(description="Evaluation attempt identifier associated with the case.")
    case_id: str = Field(description="Governed evaluation case identifier.")
    fixture_id: str = Field(description="Evaluation fixture family identifier for the case.")
    outcome: EvaluationCaseOutcome = Field(
        description="Persisted evaluation outcome for the case."
    )
    summary: str = Field(description="Human-readable explanation of the case outcome.")
    evidence_refs: list[str] = Field(
        description="Bounded evidence references supporting the recorded case outcome."
    )
    recorded_at: str = Field(description="UTC timestamp when the case outcome was recorded.")


class EvaluationApprovalFixtureSummaryDescriptor(BaseModel):
    fixture_id: str = Field(description="Evaluation fixture family identifier.")
    latest_runtime_run_id: str | None = Field(
        default=None,
        description="Most recent runtime-backed evaluation run id for this fixture family, when one exists.",
    )
    latest_runtime_recorded_at: str | None = Field(
        default=None,
        description="Timestamp of the most recent runtime-backed evaluation run for this fixture family, when one exists.",
    )
    latest_runtime_status: EvaluationRunStatus | None = Field(
        default=None,
        description="Most recent runtime-backed lifecycle status for this fixture family, when one exists.",
    )
    latest_runtime_verdict: EvaluationRunVerdict | None = Field(
        default=None,
        description="Most recent runtime-backed verdict for this fixture family, when one exists.",
    )
    evidence_state: EvaluationApprovalEvidenceState = Field(
        description="Current approval evidence posture for this specific fixture family."
    )
    notes: str = Field(
        description="Human-readable explanation of the current approval evidence posture for the fixture family."
    )


class EvaluationApprovalGateSummaryDescriptor(BaseModel):
    domain_id: str = Field(description="Stable rollout domain identifier.")
    domain_label: str = Field(description="Human-readable rollout domain label.")
    approval_ready: bool = Field(
        description="Whether the rollout domain currently has sufficient runtime-backed evaluation evidence to satisfy approval posture."
    )
    evidence_state: EvaluationApprovalEvidenceState = Field(
        description="Current overall approval evidence posture for the rollout domain."
    )
    required_fixture_count: int = Field(
        description="Number of governed fixture families required for this rollout domain."
    )
    runtime_backed_fixture_count: int = Field(
        description="Number of governed fixture families with current runtime-backed evaluation evidence."
    )
    latest_runtime_run_id: str | None = Field(
        default=None,
        description="Most recent runtime-backed evaluation run id across the rollout domain, when one exists.",
    )
    latest_runtime_recorded_at: str | None = Field(
        default=None,
        description="Timestamp of the most recent runtime-backed evaluation run across the rollout domain, when one exists.",
    )
    latest_historical_baseline_run_id: str | None = Field(
        default=None,
        description="Most recent staged historical baseline run covering the rollout domain, when one exists.",
    )
    fixture_summaries: list[EvaluationApprovalFixtureSummaryDescriptor] = Field(
        default_factory=list,
        description="Per-fixture approval evidence posture contributing to the rollout-domain summary.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable explanation of the rollout-domain approval evidence posture.",
    )


class EvaluationRunSubmissionRequest(BaseModel):
    fixture_id: str = Field(
        description="Governed evaluation fixture family identifier requested for runtime-backed submission."
    )
    caller_app: str = Field(
        description="Calling Lotus application requesting the evaluation run submission."
    )
    correlation_id: str = Field(
        description="Caller-provided correlation identifier for the evaluation run request."
    )
    triggered_by: str = Field(
        description="Operator or system identity triggering the evaluation run submission."
    )


class EvaluationRunSubmissionResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation run submission response.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    submission_status: EvaluationRunSubmissionStatus = Field(
        description="Submission outcome under the current evaluation runtime posture."
    )
    fixture_id: str = Field(
        description="Governed evaluation fixture family identifier evaluated for submission."
    )
    accepted: bool = Field(description="Whether the evaluation run submission was accepted.")
    run_id: str | None = Field(
        default=None,
        description="Assigned durable evaluation run identifier when submission is accepted.",
    )
    async_job_id: str | None = Field(
        default=None,
        description="Related async job identifier when submission is accepted.",
    )
    existing_run_id: str | None = Field(
        default=None,
        description="Existing active evaluation run identifier when a duplicate submission is rejected.",
    )
    existing_async_job_id: str | None = Field(
        default=None,
        description="Related async job identifier for the existing active evaluation run when duplicate submission is rejected.",
    )
    message: str = Field(description="Human-readable explanation of the submission outcome.")


class EvaluationRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    manifest_version: str = Field(
        description="Version identifier for the evaluation fixture manifest."
    )
    evidence_category_count: int = Field(
        description="Number of execution evidence categories currently exposed."
    )
    staged_fixture_count: int = Field(
        description="Number of evaluation fixture families currently staged."
    )
    documented_fixture_count: int = Field(
        description="Number of evaluation fixture families that remain documented-only."
    )
    staged_case_count: int = Field(
        description="Total number of concrete staged evaluation cases across all fixture families."
    )
    seam_coverage: list[EvaluationSeamCoverageDescriptor] = Field(
        description="Staged evaluation coverage summarized by major lotus-ai platform seam."
    )
    recorded_run_count: int = Field(
        description="Number of evaluation runs currently exposed across runtime-backed and historical records."
    )
    runtime_backed_run_count: int = Field(
        description="Number of durable runtime-backed evaluation runs currently exposed."
    )
    historical_run_count: int = Field(
        description="Number of historical staged-artifact evaluation runs currently exposed."
    )
    latest_recorded_run_id: str | None = Field(
        default=None,
        description="Most recent evaluation run identifier when one exists.",
    )
    latest_recorded_run_status: EvaluationRunStatus | None = Field(
        default=None,
        description="Lifecycle status for the most recent evaluation run.",
    )
    evaluation_runner_active: bool = Field(
        description="Whether a live evaluation runner is active in the current phase."
    )
    message: str = Field(
        description="Human-readable explanation of the current evaluation posture."
    )
