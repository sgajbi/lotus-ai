from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProductionBaselinePosture(str, Enum):
    LOCAL_OR_DEMO_CAPABLE = "LOCAL_OR_DEMO_CAPABLE"
    PROD_SHAPED_LOCAL = "PROD_SHAPED_LOCAL"
    PRODUCTION_READY = "PRODUCTION_READY"


class ProductionDependencyClassification(str, Enum):
    PRODUCTION_STANDARD = "PRODUCTION_STANDARD"
    FALLBACK = "FALLBACK"
    BLOCKED = "BLOCKED"


class ProductionBaselineDependencyDescriptor(BaseModel):
    dependency_id: str = Field(
        description="Stable production-baseline dependency identifier."
    )
    classification: ProductionDependencyClassification = Field(
        description="Whether the dependency currently satisfies production baseline, remains a fallback, or is blocked."
    )
    production_required: bool = Field(
        description="Whether this dependency must be production-standard before the service can be treated as production-ready."
    )
    configured_mode: str = Field(
        description="Configured mode or backend label currently selected for this dependency."
    )
    detail: str = Field(
        description="Human-readable explanation of the current dependency posture."
    )


class ProductionBaselineRuntimeStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production-baseline runtime status."
    )
    version: str = Field(description="Current lotus-ai service version.")
    posture: ProductionBaselinePosture = Field(
        description="Current top-level production-baseline posture classification."
    )
    prod_shaped_local: bool = Field(
        description="Whether the service is currently running in a deployment-shaped local posture rather than a source-run or pure local fallback posture."
    )
    production_ready: bool = Field(
        description="Whether the current posture satisfies the RFC-0020 production-standard baseline."
    )
    dependency_count: int = Field(
        description="Number of production-baseline dependency descriptors included in this response."
    )
    blocked_dependency_count: int = Field(
        description="Number of required dependencies currently classified as blocked."
    )
    fallback_dependency_count: int = Field(
        description="Number of dependencies currently classified as fallback rather than production-standard."
    )
    dependencies: list[ProductionBaselineDependencyDescriptor] = Field(
        description="Bounded inventory of the current production-baseline dependency posture."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why the service is not yet production-ready."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current production-baseline posture."
    )
