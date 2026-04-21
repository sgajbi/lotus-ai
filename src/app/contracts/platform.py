from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.app_capability_rollouts import (
    AppCapabilityRolloutCatalogGovernanceStatusResponse,
    AppCapabilityRolloutCatalogLifecycleStatusResponse,
    AppCapabilityRolloutCatalogResponse,
    AppCapabilityRolloutObservabilitySummaryResponse,
)
from app.contracts.capability_packs import (
    CapabilityPackCatalogGovernanceStatusResponse,
    CapabilityPackCatalogResponse,
)
from app.contracts.access_control import (
    AccessControlGovernanceStatusResponse,
    AccessControlRuntimeStatusResponse,
)
from app.contracts.artifacts import ArtifactGovernanceStatusResponse, ArtifactRuntimeStatusResponse
from app.contracts.async_runtime import AsyncGovernanceStatusResponse, AsyncRuntimeStatusResponse
from app.contracts.deployment_split import (
    DeploymentSplitGovernanceStatusResponse,
    DeploymentSplitRuntimeStatusResponse,
)
from app.contracts.evals import EvaluationRuntimeStatusResponse
from app.contracts.observability import (
    ObservabilityGovernanceStatusResponse,
    ObservabilityRuntimeStatusResponse,
)
from app.contracts.prompts import (
    PromptGovernanceStatusSummaryResponse,
    PromptRuntimeStatusResponse,
)
from app.contracts.production_baseline import (
    ProductionBaselineGovernanceStatusResponse,
    ProductionBaselineRuntimeStatusResponse,
)
from app.contracts.production_go_live import (
    ProductionGoLiveGovernanceStatusResponse,
    ProductionGoLiveRuntimeStatusResponse,
)
from app.contracts.providers import (
    ProviderGovernanceStatusResponse,
    ProviderOperationsStatusResponse,
)
from app.contracts.resilience import (
    ResilienceGovernanceStatusResponse,
    ResilienceRuntimeStatusResponse,
)
from app.contracts.retrieval import RetrievalGovernanceStatusResponse
from app.contracts.runtime_readiness import (
    StoreRuntimeStatusDescriptor,
)
from app.contracts.safety import SafetyGovernanceStatusResponse, SafetyRuntimeStatusResponse
from app.contracts.task_runtime import TaskRuntimeStatusResponse
from app.contracts.use_cases import (
    FirstUseCaseGovernanceStatusResponse,
    FirstUseCaseRuntimeStatusResponse,
)
from app.contracts.workflow_packs import WorkflowPackRuntimeStatusSummaryResponse


class PlatformRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the platform runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    startup_readiness_policy: str = Field(description="Configured startup readiness policy mode.")
    readiness_probe_policy: str = Field(description="Configured readiness probe degradation mode.")
    provider_mode: str = Field(description="Current model provider execution mode.")
    retrieval_mode: str = Field(description="Current retrieval execution mode.")
    embedding_provider_mode: str = Field(description="Current embedding provider mode.")
    safety_mode: str = Field(description="Current safety policy mode.")
    prompt_store_mode: str = Field(description="Current prompt registry store mode.")
    access_control_store_mode: str = Field(description="Current caller policy store mode.")
    workflow_pack_registry_store_mode: str = Field(
        description="Current workflow-pack registry store mode."
    )
    workflow_pack_run_store_mode: str = Field(description="Current workflow-pack run store mode.")
    workflow_pack_task_flow_store_mode: str = Field(
        description="Current workflow-pack task-flow store mode."
    )
    workflow_pack_queue_event_store_mode: str = Field(
        description="Current workflow-pack queue-event store mode."
    )
    artifact_store_mode: str = Field(description="Current artifact metadata store mode.")
    artifact_object_store_mode: str = Field(description="Current artifact payload store mode.")
    async_runtime: AsyncRuntimeStatusResponse = Field(
        description="Current async execution posture for lotus-ai."
    )
    artifact_runtime: ArtifactRuntimeStatusResponse = Field(
        description="Current governed artifact metadata and payload-store posture for lotus-ai."
    )
    artifact_governance: ArtifactGovernanceStatusResponse = Field(
        description="Current governed artifact activation and runbook posture for lotus-ai."
    )
    access_control_runtime: AccessControlRuntimeStatusResponse = Field(
        description="Current caller identity and access-control runtime posture for lotus-ai."
    )
    access_control_governance: AccessControlGovernanceStatusResponse = Field(
        description="Current caller identity and access-control governance posture for lotus-ai."
    )
    observability_runtime: ObservabilityRuntimeStatusResponse = Field(
        description="Current bounded observability and incident-evidence posture for lotus-ai."
    )
    observability_governance: ObservabilityGovernanceStatusResponse = Field(
        description="Current observability governance posture for lotus-ai."
    )
    async_governance: AsyncGovernanceStatusResponse = Field(
        description="Current async governance posture for lotus-ai."
    )
    provider_governance: ProviderGovernanceStatusResponse = Field(
        description="Current provider governance posture for lotus-ai."
    )
    provider_operations: ProviderOperationsStatusResponse = Field(
        description="Current provider operations posture for lotus-ai."
    )
    retrieval_governance: RetrievalGovernanceStatusResponse = Field(
        description="Current retrieval governance posture for lotus-ai."
    )
    prompt_governance: PromptGovernanceStatusSummaryResponse = Field(
        description="Current prompt governance posture for lotus-ai."
    )
    evaluation_runtime: EvaluationRuntimeStatusResponse = Field(
        description="Current evaluation runtime posture for lotus-ai."
    )
    prompt_runtime: PromptRuntimeStatusResponse = Field(
        description="Current prompt runtime selection posture for lotus-ai."
    )
    task_runtime: TaskRuntimeStatusResponse = Field(
        description="Current bounded task runtime posture for lotus-ai."
    )
    first_use_case: FirstUseCaseRuntimeStatusResponse = Field(
        description="Current first production-oriented downstream use-case contract posture."
    )
    capability_pack_catalog: CapabilityPackCatalogResponse = Field(
        description="Current app-facing capability-pack catalog layered above the generic task catalog."
    )
    capability_pack_governance: CapabilityPackCatalogGovernanceStatusResponse = Field(
        description="Current catalog-level governance posture across app-facing capability packs."
    )
    app_capability_rollout_catalog: AppCapabilityRolloutCatalogResponse = Field(
        description="Current RFC-0023 app-capability rollout catalog across downstream application pairings."
    )
    app_capability_rollout_governance: AppCapabilityRolloutCatalogGovernanceStatusResponse = Field(
        description="Current RFC-0023 catalog-level governance posture across app-capability rollout pairings."
    )
    app_capability_rollout_observability: AppCapabilityRolloutObservabilitySummaryResponse = Field(
        description="Current RFC-0023 estate-wide observability posture across app-capability rollout pairings."
    )
    app_capability_rollout_lifecycle: AppCapabilityRolloutCatalogLifecycleStatusResponse = Field(
        description="Current RFC-0023 lifecycle-discipline posture across app-capability rollout pairings."
    )
    first_use_case_governance: FirstUseCaseGovernanceStatusResponse = Field(
        description="Current bounded rollout and governance posture for the first production use case."
    )
    safety_runtime: SafetyRuntimeStatusResponse = Field(
        description="Current safety runtime posture for lotus-ai."
    )
    safety_governance: SafetyGovernanceStatusResponse = Field(
        description="Current safety governance posture for lotus-ai."
    )
    resilience_runtime: ResilienceRuntimeStatusResponse = Field(
        description="Current RFC-0017 resilience inventory and runtime continuity posture for lotus-ai."
    )
    resilience_governance: ResilienceGovernanceStatusResponse = Field(
        description="Current RFC-0017 resilience governance posture across runtime, restore, drill-evidence, activation, and runbook readiness."
    )
    production_baseline: ProductionBaselineRuntimeStatusResponse = Field(
        description="Current RFC-0020 production-baseline posture across major deployment dependencies."
    )
    deployment_split: DeploymentSplitRuntimeStatusResponse = Field(
        description="Current RFC-0015 deployment-split ownership and staged split-readiness posture."
    )
    deployment_split_governance: DeploymentSplitGovernanceStatusResponse = Field(
        description="Current RFC-0015 deployment-split governance posture across runtime, activation, runbook, and observability readiness."
    )
    production_baseline_governance: ProductionBaselineGovernanceStatusResponse = Field(
        description="Current RFC-0020 production-baseline governance posture across runtime, activation, and runbook readiness."
    )
    production_go_live: ProductionGoLiveRuntimeStatusResponse = Field(
        description="Current RFC-0022 production go-live runtime posture across platform approval and downstream use-case approval states."
    )
    production_go_live_governance: ProductionGoLiveGovernanceStatusResponse = Field(
        description="Current RFC-0022 production go-live governance posture across runtime, activation, and runbook readiness."
    )
    audit_store: StoreRuntimeStatusDescriptor = Field(
        description="Current audit persistence runtime posture."
    )
    retrieval_store: StoreRuntimeStatusDescriptor = Field(
        description="Current retrieval metadata runtime posture."
    )
    workflow_pack_registry_store: StoreRuntimeStatusDescriptor = Field(
        description="Current workflow-pack registry and control-history runtime posture."
    )
    workflow_pack_run_store: StoreRuntimeStatusDescriptor = Field(
        description="Current workflow-pack run-ledger runtime posture."
    )
    workflow_pack_task_flow_store: StoreRuntimeStatusDescriptor = Field(
        description="Current workflow-pack task-flow runtime posture."
    )
    workflow_pack_queue_event_store: StoreRuntimeStatusDescriptor = Field(
        description="Current workflow-pack queue-event history runtime posture."
    )
    workflow_pack_runtime: WorkflowPackRuntimeStatusSummaryResponse = Field(
        description="Current estate-level workflow-pack registration versus explicit execution-readiness posture."
    )
    database_configured: bool = Field(
        description="Whether a database URL is configured for durable runtime components."
    )
    prompt_count: int = Field(description="Number of registered prompt definitions.")
    capability_count: int = Field(description="Number of bounded capabilities exposed by lotus-ai.")
    capability_pack_count: int = Field(
        description="Number of app-facing capability packs currently described by lotus-ai."
    )
    app_capability_rollout_count: int = Field(
        description="Number of app-capability rollout records currently described by lotus-ai."
    )
    app_capability_rollout_ready_count: int = Field(
        description="Number of app-capability rollout records currently satisfying bounded governance posture."
    )
    app_capability_rollout_observed_count: int = Field(
        description="Number of app-capability rollout records currently showing bounded audit or async activity samples."
    )
    app_capability_rollout_lifecycle_ready_count: int = Field(
        description="Number of app-capability rollout records currently satisfying bounded lifecycle-discipline posture."
    )
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    migration_contract_enforced: bool = Field(
        description="Whether lotus-ai requires migration-managed relational schema changes."
    )
    startup_readiness_blocking: bool = Field(
        description="Whether the latest startup readiness evaluation identified blocking issues."
    )
    startup_readiness_warnings: list[str] = Field(
        description="Human-readable startup readiness findings captured during startup evaluation."
    )
