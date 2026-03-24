from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DeploymentSplitStage(str, Enum):
    UNIFIED = "UNIFIED"
    SPLIT_READY = "SPLIT_READY"
    RETRIEVAL_SPLIT_ACTIVE = "RETRIEVAL_SPLIT_ACTIVE"
    RETRIEVAL_AND_EVALS_SPLIT_ACTIVE = "RETRIEVAL_AND_EVALS_SPLIT_ACTIVE"


class DeploymentPlaneId(str, Enum):
    RUNTIME = "runtime"
    RETRIEVAL = "retrieval"
    EVALS = "evals"


class DeploymentPlaneOwnershipDescriptor(BaseModel):
    plane_id: DeploymentPlaneId = Field(description="Stable internal deployment plane identifier.")
    externally_addressable: bool = Field(
        description="Whether the plane remains part of the single external lotus-ai front-door contract."
    )
    separately_deployed: bool = Field(
        description="Whether the plane is currently described as independently deployed rather than still unified."
    )
    split_ready: bool = Field(
        description="Whether the plane is currently modeled as split-ready even if it remains unified."
    )
    owned_domains: list[str] = Field(
        description="Bounded list of the primary runtime or governance domains owned by this plane."
    )
    shared_responsibilities: list[str] = Field(
        description="Bounded list of shared cross-plane responsibilities that remain coherent across all planes."
    )


class DeploymentRouteMode(str, Enum):
    UNIFIED_INTERNAL = "UNIFIED_INTERNAL"
    SPLIT_READY_UNIFIED = "SPLIT_READY_UNIFIED"
    PLANE_SPLIT_ACTIVE = "PLANE_SPLIT_ACTIVE"


class DeploymentRouteDescriptor(BaseModel):
    route_id: str = Field(description="Stable internal deployment-routing descriptor identifier.")
    owning_plane: DeploymentPlaneId = Field(
        description="Internal plane currently responsible for executing the routed workload."
    )
    route_mode: DeploymentRouteMode = Field(
        description="Whether the route is still unified, split-ready while still unified, or actively split."
    )
    rollback_target_stage: DeploymentSplitStage = Field(
        description="Deployment-split stage that operators should roll back to if this route becomes unhealthy."
    )
    degraded: bool = Field(
        description="Whether this route is currently active in a degraded split-plane posture."
    )
    degraded_findings: list[str] = Field(
        description="Human-readable findings describing why the route is degraded under the active split posture."
    )
    detail: str = Field(description="Human-readable explanation of the current route posture.")


class DeploymentSplitRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the deployment-split runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    configured_stage: DeploymentSplitStage = Field(
        description="Configured internal deployment-split stage requested for the current runtime."
    )
    effective_stage: DeploymentSplitStage = Field(
        description="Effective deployment-split stage currently supportable by the implementation and runtime posture."
    )
    front_door_plane: DeploymentPlaneId = Field(
        description="Plane that continues to own the unified external lotus-ai contract surface."
    )
    split_ready: bool = Field(
        description="Whether the current runtime posture is at least split-ready, even if no plane cutover is active yet."
    )
    plane_count: int = Field(description="Number of governed deployment planes described by this RFC.")
    separate_plane_count: int = Field(
        description="Number of planes currently described as independently deployed rather than unified."
    )
    route_count: int = Field(
        description="Number of bounded internal routing descriptors covered by the current split posture."
    )
    planes: list[DeploymentPlaneOwnershipDescriptor] = Field(
        description="Bounded plane-ownership descriptors for runtime, retrieval, and eval deployment planes."
    )
    routes: list[DeploymentRouteDescriptor] = Field(
        description="Bounded internal routing descriptors for retrieval and eval split-aware flows."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why the configured split stage is not yet the effective split posture."
    )
    degraded: bool = Field(
        description="Whether the current effective split posture is active but degraded."
    )
    degraded_findings: list[str] = Field(
        description="Human-readable degraded findings that still preserve the currently active split posture."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current deployment-split posture."
    )


class DeploymentSplitActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the deployment-split activation-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    configured_stage: DeploymentSplitStage = Field(
        description="Configured internal deployment-split stage requested for the current runtime."
    )
    effective_stage: DeploymentSplitStage = Field(
        description="Effective deployment-split stage currently supportable by the implementation and runtime posture."
    )
    split_ready: bool = Field(
        description="Whether the current runtime posture is at least split-ready."
    )
    split_active: bool = Field(
        description="Whether the current effective stage currently has one or more active split planes."
    )
    activation_ready: bool = Field(
        description="Whether the configured deployment-split stage is activatable without blocked or degraded split posture."
    )
    degraded: bool = Field(
        description="Whether the current effective stage remains active but degraded."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why the configured deployment-split stage is not yet activatable."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before the configured deployment-split stage can be treated as activatable."
    )


class DeploymentSplitRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable deployment-split runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before the current deployment-split stage can be treated as activatable."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class DeploymentSplitRunbookReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the deployment-split runbook-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether deployment-split operational runbook readiness is sufficient for the current configured stage."
    )
    required_item_count: int = Field(
        description="Number of deployment-split runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required deployment-split runbook items currently marked complete."
    )
    items: list[DeploymentSplitRunbookReadinessItem] = Field(
        description="Governed deployment-split operational runbook readiness items."
    )


class DeploymentSplitGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the deployment-split governance status.")
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether deployment-split governance is ready for the configured stage."
    )
    runtime_status: DeploymentSplitRuntimeStatusResponse = Field(
        description="Current runtime-backed deployment-split posture."
    )
    activation_readiness: DeploymentSplitActivationReadinessResponse = Field(
        description="Current activation-readiness posture for the configured deployment-split stage."
    )
    runbook_readiness: DeploymentSplitRunbookReadinessResponse = Field(
        description="Current runbook-readiness posture for the deployment-split stage."
    )
    observability_governance_ready: bool = Field(
        description="Whether cross-plane observability governance is ready to support the configured deployment-split stage."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking the configured deployment-split stage."
    )
    governance_summary: list[str] = Field(
        description="Short operator-facing summary of the current deployment-split governance posture."
    )
