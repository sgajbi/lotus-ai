from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.artifacts import ArtifactDescriptor


class ObservabilityPosture(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ObservabilityFreshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class AISurfaceSupportabilityReason(str, Enum):
    NO_SENSITIVE_TELEMETRY_DEGRADED = "NO_SENSITIVE_TELEMETRY_DEGRADED"
    WORKFLOW_PACK_ACTION_REQUIRED = "WORKFLOW_PACK_ACTION_REQUIRED"
    WORKFLOW_PACK_READY = "WORKFLOW_PACK_READY"
    WORKFLOW_PACK_HISTORICAL = "WORKFLOW_PACK_HISTORICAL"
    WORKFLOW_PACK_SUPPORTED_NO_ACTIVITY = "WORKFLOW_PACK_SUPPORTED_NO_ACTIVITY"


class ObservabilityDomainId(str, Enum):
    PROVIDER = "provider"
    RETRIEVAL = "retrieval"
    ASYNC = "async"
    EVALUATION = "evaluation"
    PROMPT = "prompt"
    SAFETY = "safety"


class ObservabilityBreakdownSupport(BaseModel):
    caller_app_supported: bool = Field(
        description="Whether bounded caller-app summaries are supported for the domain."
    )
    tenant_supported: bool = Field(
        description="Whether bounded tenant summaries are supported for the domain."
    )
    capability_supported: bool = Field(
        description="Whether bounded capability/task/source summaries are supported for the domain."
    )


class DomainTelemetrySummary(BaseModel):
    domain_id: ObservabilityDomainId = Field(
        description="Stable platform domain represented by the telemetry summary."
    )
    posture: ObservabilityPosture = Field(
        description="Current observability posture for the domain."
    )
    freshness: ObservabilityFreshness = Field(
        description="Freshness posture for the bounded telemetry summary."
    )
    telemetry_sources: list[str] = Field(
        description="Bounded list of runtime or durable sources used to assemble the summary."
    )
    incident_evidence_supported: bool = Field(
        description="Whether the domain already has bounded incident-evidence support in the observability layer."
    )
    incident_signal_count: int = Field(
        description="Number of bounded incident signals currently surfaced for the domain."
    )
    breakdown_support: ObservabilityBreakdownSupport = Field(
        description="Caller, tenant, and capability breakdown support for the domain."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing explanation of the current telemetry posture."
    )


class IncidentEvidenceSummaryItem(BaseModel):
    domain_id: ObservabilityDomainId = Field(
        description="Stable domain owning the incident-evidence item."
    )
    evidence_id: str = Field(description="Stable incident-evidence identifier.")
    posture: ObservabilityPosture = Field(
        description="Current posture for the bounded incident-evidence item."
    )
    freshness: ObservabilityFreshness = Field(
        description="Freshness posture for the incident-evidence item."
    )
    durable: bool = Field(
        description="Whether the evidence item is assembled from durable state rather than volatile-only telemetry."
    )
    artifact_refs: list[ArtifactDescriptor] = Field(
        default_factory=list,
        description="Governed artifact descriptors attached to the bounded incident-evidence item.",
    )
    summary: str = Field(description="Human-readable explanation of the incident-evidence item.")


class DomainIncidentSummaryResponse(BaseModel):
    service: str = Field(description="Service name emitting the domain incident summary.")
    version: str = Field(description="Current lotus-ai service version.")
    domain_id: ObservabilityDomainId = Field(
        description="Stable platform domain represented by the incident summary."
    )
    telemetry: DomainTelemetrySummary = Field(
        description="Bounded telemetry summary for the domain."
    )
    incident_evidence_items: list[IncidentEvidenceSummaryItem] = Field(
        description="Bounded incident-evidence items currently exposed for the domain."
    )
    linked_endpoints: list[str] = Field(
        description="Existing platform endpoints that provide deeper runtime or governance inspection for the domain."
    )
    summary: list[str] = Field(description="Short operator-facing incident summary for the domain.")


class ObservabilityCapabilityKind(str, Enum):
    TASK = "TASK"
    RETRIEVAL_SOURCE = "RETRIEVAL_SOURCE"
    ASYNC_JOB_TYPE = "ASYNC_JOB_TYPE"


class ObservabilityCallerBreakdownSample(BaseModel):
    caller_app: str = Field(description="Caller application represented in the bounded sample.")
    execution_count: int = Field(
        description="Number of sampled task executions associated with the caller."
    )
    allowed_execution_count: int = Field(
        description="Number of sampled task executions with an allowed authorization decision."
    )
    retrieval_execution_count: int = Field(
        description="Number of sampled retrieval-backed task executions for the caller."
    )
    live_provider_execution_count: int = Field(
        description="Number of sampled live-provider task executions for the caller."
    )
    async_job_count: int = Field(
        description="Number of sampled async jobs associated with the caller."
    )


class ObservabilityModelBreakdownSample(BaseModel):
    model_id: str = Field(description="Provider-reported model identity, or 'unknown'.")
    execution_count: int = Field(description="Sampled executions attributed to this model.")
    priced_execution_count: int = Field(
        description="Sampled executions with a rate-card-priced cost (issue #178 S4)."
    )
    estimated_cost_usd_total: float = Field(
        description="Sum of rate-card-estimated costs over the sampled executions."
    )


class ObservabilityTenantBreakdownSample(BaseModel):
    tenant_id: str = Field(description="Tenant identifier represented in the bounded sample.")
    execution_count: int = Field(
        description="Number of sampled authorized task executions associated with the tenant."
    )
    caller_app_count: int = Field(
        description="Number of distinct caller applications represented for the tenant."
    )
    priced_execution_count: int = Field(
        default=0,
        description="Sampled executions with a rate-card-priced cost (issue #178 S4).",
    )
    estimated_cost_usd_total: float = Field(
        default=0.0,
        description="Sum of rate-card-estimated costs over the sampled executions.",
    )
    capability_count: int = Field(
        description="Number of distinct task capabilities represented for the tenant."
    )


class ObservabilityCapabilityBreakdownSample(BaseModel):
    capability_kind: ObservabilityCapabilityKind = Field(
        description="Kind of capability represented in the bounded sample."
    )
    capability_id: str = Field(
        description="Stable task id, retrieval source id, or async job type represented in the sample."
    )
    observed_count: int = Field(
        description="Number of sampled observations associated with the capability."
    )
    priced_execution_count: int = Field(
        default=0,
        description="Sampled executions with a rate-card-priced cost (issue #178 S4).",
    )
    estimated_cost_usd_total: float = Field(
        default=0.0,
        description="Sum of rate-card-estimated costs over the sampled executions.",
    )


class ObservabilityBreakdownSummaryResponse(BaseModel):
    service: str = Field(description="Service name emitting the observability breakdown summary.")
    version: str = Field(description="Current lotus-ai service version.")
    sampled_audit_record_limit: int = Field(
        description="Maximum number of recent audit records included in the bounded breakdown sample."
    )
    sampled_audit_record_count: int = Field(
        description="Number of recent audit records actually included in the bounded breakdown sample."
    )
    tenant_scope: str = Field(
        description="Audit-read scope mode the breakdown was computed under (caller-derived).",
    )
    sampled_async_job_count: int = Field(
        description="Number of async job records included in the bounded breakdown sample."
    )
    tenant_breakdown_policy: str = Field(
        description="How tenant visibility is bounded by current authorization-aware observability rules."
    )
    caller_apps: list[ObservabilityCallerBreakdownSample] = Field(
        description="Bounded caller-app breakdown across recent task executions and async jobs."
    )
    tenants: list[ObservabilityTenantBreakdownSample] = Field(
        description="Bounded tenant breakdown derived only from authorized task executions carrying tenant identity."
    )
    models: list[ObservabilityModelBreakdownSample] = Field(
        default_factory=list,
        description="Per-model execution and rate-card cost breakdown over the sample "
        "(issue #178 S4).",
    )
    capabilities: list[ObservabilityCapabilityBreakdownSample] = Field(
        description="Bounded capability breakdown across tasks, retrieval sources, and async job types."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of current caller, tenant, and capability breakdown coverage."
    )


class ObservabilityIncidentSummaryResponse(BaseModel):
    service: str = Field(description="Service name emitting the observability incident summary.")
    version: str = Field(description="Current lotus-ai service version.")
    domain_count: int = Field(
        description="Number of domain incident summaries included in the response."
    )
    degraded_domain_count: int = Field(
        description="Number of domain incident summaries currently reporting degraded posture."
    )
    summaries: list[DomainIncidentSummaryResponse] = Field(
        description="Bounded incident summaries for the currently implemented observability domains."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of current incident-evidence coverage."
    )


class AISurfaceSupportabilityItem(BaseModel):
    surface_id: str = Field(description="Stable AI-backed product or workflow surface identifier.")
    owning_service: str = Field(description="Service that owns the surface contract.")
    workflow_authority_owner: str = Field(
        description="Service or composition layer that retains consequence-bearing workflow authority."
    )
    workflow_pack_ref: str = Field(
        description="Workflow-pack version reference grounding this supportability item."
    )
    supportability_status: str = Field(
        description="Current supportability posture for this AI-backed surface."
    )
    supportability_reason: AISurfaceSupportabilityReason = Field(
        description=(
            "Bounded reason explaining why the current supportability posture was assigned."
        )
    )
    model_posture: ObservabilityPosture = Field(
        description="Current model/provider posture relevant to the AI-backed surface."
    )
    latest_ready_run_id: str | None = Field(
        default=None,
        description="Latest ready workflow-pack run for this surface, when available.",
    )
    latest_action_required_run_id: str | None = Field(
        default=None,
        description="Latest actionable workflow-pack run for this surface, when available.",
    )
    no_sensitive_content_telemetry: bool = Field(
        description="Whether the item is covered by bounded no-sensitive-content telemetry and redaction posture."
    )
    source_endpoints: list[str] = Field(
        description="Bounded source endpoints operators can inspect for this supportability item."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of this surface supportability item."
    )


class AISurfaceSupportabilitySummary(BaseModel):
    posture: ObservabilityPosture = Field(
        description="Overall AI surface supportability posture across supported AI-backed surfaces."
    )
    freshness: ObservabilityFreshness = Field(
        description="Freshness posture for the source-backed AI surface supportability summary."
    )
    supported_surface_count: int = Field(
        description="Number of AI-backed surfaces represented in the supportability summary."
    )
    executable_workflow_pack_count: int = Field(
        description="Number of explicitly executable workflow-pack versions represented by the supportability summary."
    )
    action_required_surface_count: int = Field(
        description="Number of represented surfaces that currently require operator action."
    )
    unavailable_surface_count: int = Field(
        description="Number of represented surfaces whose source supportability posture is unavailable."
    )
    no_sensitive_content_telemetry: bool = Field(
        description="Whether all represented surfaces remain covered by bounded no-sensitive-content telemetry posture."
    )
    metric_name: str = Field(
        description="Prometheus metric emitted for bounded AI surface supportability posture."
    )
    metric_labels: list[str] = Field(
        description=(
            "Governed bounded Prometheus labels emitted by the AI surface supportability metric."
        )
    )
    surfaces: list[AISurfaceSupportabilityItem] = Field(
        description="Bounded source-backed AI surface supportability items."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of AI surface supportability posture."
    )


class ObservabilityRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the observability runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    posture: ObservabilityPosture = Field(
        description="Current overall observability posture for lotus-ai."
    )
    freshness: ObservabilityFreshness = Field(
        description="Current overall freshness posture for the observability layer."
    )
    domain_count: int = Field(
        description="Number of observability domains summarized in this response."
    )
    healthy_domain_count: int = Field(
        description="Number of summarized domains currently reporting healthy observability posture."
    )
    degraded_domain_count: int = Field(
        description="Number of summarized domains currently reporting degraded observability posture."
    )
    unavailable_domain_count: int = Field(
        description="Number of summarized domains currently reporting unavailable observability posture."
    )
    incident_evidence_supported_domain_count: int = Field(
        description="Number of summarized domains already carrying bounded incident-evidence support."
    )
    domains: list[DomainTelemetrySummary] = Field(
        description="Bounded per-domain telemetry summaries for the current observability layer."
    )
    incident_evidence_items: list[IncidentEvidenceSummaryItem] = Field(
        description="Bounded incident-evidence items currently exposed by the observability layer."
    )
    ai_surface_supportability: AISurfaceSupportabilitySummary = Field(
        description="RFC-0108 source-backed supportability posture for AI-backed product and workflow surfaces."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current observability layer posture."
    )


class ObservabilityActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the observability activation-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    posture: ObservabilityPosture = Field(
        description="Current overall observability posture for lotus-ai."
    )
    freshness: ObservabilityFreshness = Field(
        description="Current overall freshness posture for lotus-ai."
    )
    activation_ready: bool = Field(
        description="Whether the observability layer is durable enough for governed platform rollout."
    )
    domain_count: int = Field(
        description="Number of observability domains summarized in this response."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why observability governance is not yet fully activatable."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before observability rollout is fully ready."
    )


class ObservabilityRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable observability runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before full observability activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class ObservabilityRunbookReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the observability runbook readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether observability operational runbook readiness is sufficient for full activation."
    )
    required_item_count: int = Field(
        description="Number of observability runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required observability runbook items currently marked complete."
    )
    items: list[ObservabilityRunbookReadinessItem] = Field(
        description="Governed observability operational runbook readiness items."
    )


class ObservabilityGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the observability governance status.")
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether observability governance is ready for fully governed rollout."
    )
    runtime_status: ObservabilityRuntimeStatusResponse = Field(
        description="Current runtime-backed observability posture."
    )
    activation_readiness: ObservabilityActivationReadinessResponse = Field(
        description="Current activation-readiness posture for observability rollout."
    )
    runbook_readiness: ObservabilityRunbookReadinessResponse = Field(
        description="Current runbook-readiness posture for observability rollout."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking stronger observability posture."
    )
    governance_summary: list[str] = Field(
        description="Short operator-facing summary of current observability governance posture."
    )
