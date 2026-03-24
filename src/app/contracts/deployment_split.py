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
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current deployment-split posture."
    )
