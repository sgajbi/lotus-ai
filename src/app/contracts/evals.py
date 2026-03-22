from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvaluationAssetStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    STAGED = "STAGED"


class EvaluationEvidenceCategoryDescriptor(BaseModel):
    category_id: str = Field(description="Stable execution evidence category identifier.")
    description: str = Field(description="Human-readable description of the evidence category.")


class EvaluationFixtureDescriptor(BaseModel):
    fixture_id: str = Field(description="Stable evaluation fixture family identifier.")
    status: EvaluationAssetStatus = Field(
        description="Current maturity status for the fixture family."
    )
    description: str = Field(description="Human-readable description of the fixture family.")


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
    evaluation_runner_active: bool = Field(
        description="Whether a live evaluation runner is active in the current phase."
    )
    message: str = Field(
        description="Human-readable explanation of the current evaluation posture."
    )
