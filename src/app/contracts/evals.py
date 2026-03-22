from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvaluationAssetStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    STAGED = "STAGED"


class EvaluationRunStatus(str, Enum):
    RECORDED = "RECORDED"
    SUPERSEDED = "SUPERSEDED"


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
    recorded_at: str = Field(description="UTC timestamp when the evaluation artifact was recorded.")
    status: EvaluationRunStatus = Field(
        description="Lifecycle status for the recorded evaluation artifact."
    )
    manifest_version: str = Field(
        description="Evaluation fixture manifest version associated with the recorded artifact."
    )
    staged_fixture_count: int = Field(
        description="Number of staged fixture families represented in the recorded artifact."
    )
    staged_case_count: int = Field(
        description="Number of staged cases represented in the recorded artifact."
    )
    seam_coverage: list[EvaluationSeamCoverageDescriptor] = Field(
        description="Seam-oriented coverage captured in the recorded evaluation artifact."
    )
    notes: str = Field(
        description="Human-readable description of the recorded evaluation artifact."
    )


class EvaluationRunCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation run catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    run_count: int = Field(
        description="Number of recorded evaluation run artifacts currently exposed."
    )
    latest_run_id: str | None = Field(
        default=None,
        description="Most recent evaluation run artifact identifier when one exists.",
    )
    runs: list[EvaluationRunArtifactDescriptor] = Field(
        description="Recorded evaluation run artifacts available for inspection."
    )


class EvaluationRunDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the evaluation run detail.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    run: EvaluationRunArtifactDescriptor = Field(
        description="Recorded evaluation run artifact detail."
    )


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
        description="Number of recorded evaluation run artifacts currently exposed."
    )
    latest_recorded_run_id: str | None = Field(
        default=None,
        description="Most recent recorded evaluation run artifact identifier when one exists.",
    )
    latest_recorded_run_status: EvaluationRunStatus | None = Field(
        default=None,
        description="Lifecycle status for the most recent recorded evaluation run artifact.",
    )
    evaluation_runner_active: bool = Field(
        description="Whether a live evaluation runner is active in the current phase."
    )
    message: str = Field(
        description="Human-readable explanation of the current evaluation posture."
    )
