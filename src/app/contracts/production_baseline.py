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


class ProductionBaselineActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production-baseline activation-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    posture: ProductionBaselinePosture = Field(
        description="Current top-level production-baseline posture classification."
    )
    prod_shaped_local: bool = Field(
        description="Whether the service currently satisfies the deployment-shaped local baseline."
    )
    production_ready: bool = Field(
        description="Whether the current posture satisfies the full RFC-0020 production baseline."
    )
    activation_ready: bool = Field(
        description="Whether the current runtime posture is activatable as the accepted production baseline."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why the production baseline is not yet activatable."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before the production baseline can be treated as activatable."
    )


class ProductionBaselineRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(
        description="Stable production-baseline runbook readiness item identifier."
    )
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before the production baseline can be treated as activatable."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class ProductionBaselineRunbookReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production-baseline runbook-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether production-baseline operational runbook readiness is sufficient for go-live posture."
    )
    required_item_count: int = Field(
        description="Number of production-baseline runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required production-baseline runbook items currently marked complete."
    )
    items: list[ProductionBaselineRunbookReadinessItem] = Field(
        description="Governed production-baseline operational runbook readiness items."
    )


class ProductionBaselineGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the production-baseline governance status.")
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether production-baseline governance is ready for accepted go-live posture."
    )
    runtime_status: ProductionBaselineRuntimeStatusResponse = Field(
        description="Current runtime-backed production-baseline posture."
    )
    activation_readiness: ProductionBaselineActivationReadinessResponse = Field(
        description="Current activation-readiness posture for the production baseline."
    )
    runbook_readiness: ProductionBaselineRunbookReadinessResponse = Field(
        description="Current runbook-readiness posture for the production baseline."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking the accepted production baseline."
    )
    governance_summary: list[str] = Field(
        description="Short operator-facing summary of current production-baseline governance posture."
    )
