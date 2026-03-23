from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.evals import EvaluationApprovalGateSummaryDescriptor
from app.contracts.runtime_readiness import RuntimeReadinessStatus


class RetrievalSourceKind(str, Enum):
    RFC = "RFC"
    STANDARD = "STANDARD"
    ARCHITECTURE = "ARCHITECTURE"
    OPENAPI = "OPENAPI"


class RetrievalStatus(str, Enum):
    DISABLED = "DISABLED"
    READY = "READY"
    REJECTED = "REJECTED"


class RetrievalIndexStatus(str, Enum):
    NOT_INDEXED = "NOT_INDEXED"
    STAGED = "STAGED"
    INDEXED = "INDEXED"


class RetrievalJobStatus(str, Enum):
    PENDING = "PENDING"
    STAGED = "STAGED"
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class RetrievalPipelineStage(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    STAGED = "STAGED"
    ENABLED = "ENABLED"


class RetrievalSourceDescriptor(BaseModel):
    source_id: str = Field(description="Stable retrieval source identifier.")
    kind: RetrievalSourceKind = Field(description="High-level source category.")
    enabled: bool = Field(description="Whether the source is currently enabled for search.")
    description: str = Field(description="Human-readable source description.")


class RetrievalSourceCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval source catalog.")
    retrieval_mode: str = Field(description="Current retrieval mode configured for lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    sources: list[RetrievalSourceDescriptor] = Field(
        description="Approved retrieval source descriptors known to lotus-ai."
    )


class RetrievalSourceGovernanceDescriptor(BaseModel):
    source_id: str = Field(description="Stable retrieval source identifier.")
    kind: RetrievalSourceKind = Field(description="High-level source category.")
    governance_status: str = Field(
        description="Derived governance posture for the source within the current live-search rollout."
    )
    search_enabled: bool = Field(
        description="Whether the source currently has any document eligible for live retrieval search."
    )
    document_count: int = Field(description="Number of staged documents currently registered.")
    chunk_count: int = Field(description="Number of staged chunks currently registered.")
    index_status: RetrievalIndexStatus = Field(description="Current staged indexing status.")
    notes: str = Field(description="Human-readable explanation of the source governance posture.")


class RetrievalDocumentGovernanceDescriptor(BaseModel):
    document_id: str = Field(description="Stable retrieval document identifier.")
    source_id: str = Field(description="Retrieval source identifier for the document.")
    title: str = Field(description="Human-readable document title.")
    governance_status: str = Field(
        description="Derived governance posture for the document within the current live-search rollout."
    )
    search_enabled: bool = Field(
        description="Whether the document is currently eligible for live retrieval search."
    )
    chunk_count: int = Field(description="Current chunk count registered for the document.")
    index_status: RetrievalIndexStatus = Field(description="Current indexing status for the document.")
    notes: str = Field(description="Human-readable explanation of the document governance posture.")


class RetrievalDocumentGovernanceResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval document governance view.")
    retrieval_mode: str = Field(description="Current retrieval mode configured for lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    searchable_document_count: int = Field(
        description="Number of documents currently eligible for live retrieval search."
    )
    index_pending_document_count: int = Field(
        description="Number of source-enabled documents still blocked on indexing."
    )
    blocked_document_count: int = Field(
        description="Number of documents currently blocked from live search by source posture."
    )
    documents: list[RetrievalDocumentGovernanceDescriptor] = Field(
        description="Per-document governance posture for the currently registered retrieval corpus."
    )


class RetrievalSourceGovernanceResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval source governance view.")
    retrieval_mode: str = Field(description="Current retrieval mode configured for lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    searchable_source_count: int = Field(
        description="Number of sources currently contributing at least one document to live retrieval search."
    )
    index_pending_source_count: int = Field(
        description="Number of source-enabled sources still blocked on indexing before live search."
    )
    blocked_source_count: int = Field(
        description="Number of sources currently blocked from live search by source posture."
    )
    empty_source_count: int = Field(description="Number of sources with no staged documents yet.")
    sources: list[RetrievalSourceGovernanceDescriptor] = Field(
        description="Per-source governance posture for the currently registered retrieval corpus."
    )


class RetrievalDocumentDescriptor(BaseModel):
    document_id: str = Field(description="Stable retrieval document identifier.")
    source_id: str = Field(description="Retrieval source identifier for the document.")
    title: str = Field(description="Human-readable title for the document.")
    location: str = Field(description="Repository-relative or logical location of the document.")
    chunk_count: int = Field(description="Current staged chunk count for the document.")
    index_status: RetrievalIndexStatus = Field(description="Indexing status for the document.")


class RetrievalChunkDescriptor(BaseModel):
    chunk_id: str = Field(description="Stable chunk identifier.")
    document_id: str = Field(description="Parent retrieval document identifier.")
    source_id: str = Field(description="Parent retrieval source identifier.")
    chunk_order: int = Field(description="Stable chunk order within the document.")
    token_estimate: int = Field(description="Estimated token count for the chunk.")
    preview: str = Field(description="Short preview of the chunk contents.")
    index_status: RetrievalIndexStatus = Field(description="Indexing status for the chunk.")


class RetrievalChunkCatalogResponse(BaseModel):
    document_id: str = Field(description="Parent retrieval document identifier.")
    source_id: str = Field(description="Parent retrieval source identifier.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    chunks: list[RetrievalChunkDescriptor] = Field(
        description="Known chunks currently staged for the document."
    )


class RetrievalDocumentCatalogResponse(BaseModel):
    source_id: str = Field(description="Retrieval source identifier for the returned documents.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    documents: list[RetrievalDocumentDescriptor] = Field(
        description="Known documents currently staged under the retrieval source."
    )


class RetrievalSourceStatusDescriptor(BaseModel):
    source_id: str = Field(description="Retrieval source identifier.")
    index_status: RetrievalIndexStatus = Field(description="Current source-level indexing status.")
    document_count: int = Field(description="Number of staged documents in the source.")
    chunk_count: int = Field(description="Total staged chunk count across the source.")


class RetrievalIndexStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval index status.")
    retrieval_mode: str = Field(description="Current retrieval mode configured for lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    sources: list[RetrievalSourceStatusDescriptor] = Field(
        description="Source-level indexing status details."
    )


class RetrievalIndexJobDescriptor(BaseModel):
    job_id: str = Field(description="Stable retrieval indexing job identifier.")
    source_id: str = Field(description="Retrieval source identifier owned by the job.")
    status: RetrievalJobStatus = Field(description="Current status for the indexing job.")
    document_count: int = Field(description="Number of staged documents covered by the job.")
    chunk_count: int = Field(description="Number of staged chunks covered by the job.")
    message: str = Field(description="Human-readable job status message.")


class RetrievalIndexJobCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval job catalog.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    jobs: list[RetrievalIndexJobDescriptor] = Field(
        description="Known retrieval indexing jobs for the staged corpus."
    )


class RetrievalIndexJobStepDescriptor(BaseModel):
    step_id: str = Field(description="Stable retrieval indexing step identifier.")
    name: str = Field(description="Human-readable retrieval indexing step name.")
    stage: RetrievalPipelineStage = Field(description="Current lifecycle stage for the step.")
    runtime_status: str | None = Field(
        default=None,
        description="Optional runtime-backed async status for this retrieval indexing step.",
    )
    linked_async_job_id: str | None = Field(
        default=None,
        description="Optional linked async job identifier when the step is driven by the durable async runtime.",
    )
    description: str = Field(description="Human-readable explanation of the step.")


class RetrievalIndexJobDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval job detail.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    embedding_provider_mode: str = Field(description="Current embedding provider mode.")
    job: RetrievalIndexJobDescriptor = Field(description="Retrieval indexing job descriptor.")
    steps: list[RetrievalIndexJobStepDescriptor] = Field(
        description="Ordered retrieval indexing steps for the job."
    )


class RetrievalIndexingPolicyResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval indexing policy.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    retrieval_mode: str = Field(description="Current retrieval mode configured for lotus-ai.")
    retrieval_store_mode: str = Field(description="Current retrieval metadata store mode.")
    embedding_provider_mode: str = Field(description="Current embedding provider mode.")
    chunking_strategy: str = Field(description="Current chunking strategy label.")
    embedding_strategy: str = Field(description="Current embedding strategy label.")
    persistence_strategy: str = Field(description="Current vector persistence strategy label.")
    execution_stage: RetrievalPipelineStage = Field(
        description="Current overall lifecycle stage for retrieval indexing."
    )
    notes: list[str] = Field(
        description="Important governance notes describing current retrieval indexing constraints."
    )


class RetrievalRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval runtime status.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    retrieval_mode: str = Field(description="Current retrieval execution mode.")
    retrieval_store_mode: str = Field(description="Current retrieval metadata store mode.")
    retrieval_store_status: RuntimeReadinessStatus = Field(
        description="Readiness status for the active retrieval metadata store."
    )
    retrieval_store_detail: str = Field(
        description="Human-readable explanation of the retrieval store readiness state."
    )
    database_configured: bool = Field(
        description="Whether a database URL is configured for durable retrieval metadata."
    )
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    source_count: int = Field(
        description="Number of retrieval sources visible through the active store."
    )
    document_count: int = Field(
        description="Number of retrieval documents visible through the active store."
    )
    chunk_count: int = Field(
        description="Number of retrieval chunks visible through the active store."
    )
    index_job_count: int = Field(
        description="Number of retrieval indexing jobs visible through the active store."
    )


class RetrievalSearchRequest(BaseModel):
    query: str = Field(description="Search query provided by the caller.")
    caller_app: str = Field(description="Calling Lotus application requesting retrieval.")
    correlation_id: str = Field(description="Correlation identifier for the retrieval request.")
    source_ids: list[str] = Field(
        default_factory=list,
        description="Optional source filters limiting retrieval to approved source ids.",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of hits requested.")


class RetrievalSearchHit(BaseModel):
    source_id: str = Field(description="Retrieval source identifier that produced the hit.")
    document_id: str = Field(description="Retrieval document identifier that produced the hit.")
    chunk_id: str = Field(description="Retrieval chunk identifier that produced the hit.")
    score: float = Field(description="Relevance score associated with the hit.")
    snippet: str = Field(description="Short snippet preview for the hit.")


class RetrievalSearchResponse(BaseModel):
    status: RetrievalStatus = Field(description="Current retrieval execution status.")
    query: str = Field(description="Original caller query.")
    execution_stage: "RetrievalExecutionStage" = Field(
        description="Current retrieval execution stage applied to the request."
    )
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    hits: list[RetrievalSearchHit] = Field(description="Retrieval hits returned by the search.")
    message: str = Field(description="Human-readable retrieval status message.")


class RetrievalExecutionStage(str, Enum):
    CATALOG_ONLY = "CATALOG_ONLY"
    LIVE_SEARCH = "LIVE_SEARCH"
    SEARCH_DISABLED = "SEARCH_DISABLED"
    INDEXING_DISABLED = "INDEXING_DISABLED"


class RetrievalExecutionRequest(BaseModel):
    query: str = Field(description="Search query provided by the caller.")
    caller_app: str = Field(description="Calling Lotus application requesting retrieval.")
    correlation_id: str = Field(description="Correlation identifier for the retrieval request.")
    source_ids: list[str] = Field(
        default_factory=list,
        description="Optional source filters limiting retrieval to approved source ids.",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of hits requested.")


class RetrievalExecutionResponse(BaseModel):
    status: RetrievalStatus = Field(description="Execution outcome for the retrieval request.")
    execution_stage: RetrievalExecutionStage = Field(
        description="Current retrieval execution stage applied to the request."
    )
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    hits: list[RetrievalSearchHit] = Field(description="Retrieval hits returned by the gateway.")
    message: str = Field(description="Human-readable retrieval execution message.")


class RetrievalExecutionStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval execution status.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    retrieval_mode: str = Field(description="Configured retrieval execution mode.")
    execution_stage: RetrievalExecutionStage = Field(
        description="Current staged retrieval execution posture."
    )
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    live_search_enabled: bool = Field(description="Whether live retrieval search is active.")
    live_indexing_enabled: bool = Field(description="Whether live retrieval indexing is active.")
    message: str = Field(description="Human-readable explanation of the retrieval execution state.")


class RetrievalActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the retrieval activation readiness view."
    )
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    retrieval_mode: str = Field(description="Configured retrieval execution mode.")
    embedding_provider_mode: str = Field(description="Configured embedding provider mode.")
    activation_ready: bool = Field(
        description="Whether live retrieval execution is currently ready for activation."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why retrieval execution is not yet activatable."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before live retrieval execution can be enabled."
    )


class RetrievalRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable retrieval runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before live retrieval activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class RetrievalRunbookReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval runbook readiness view.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    runbook_ready: bool = Field(
        description="Whether retrieval operational runbook readiness is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of retrieval runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required retrieval runbook items currently marked complete."
    )
    items: list[RetrievalRunbookReadinessItem] = Field(
        description="Governed retrieval operational runbook readiness items."
    )


class RetrievalEvidenceReadinessItem(BaseModel):
    evidence_id: str = Field(description="Stable retrieval evidence-readiness item identifier.")
    status: str = Field(description="Current readiness posture for the evidence requirement.")
    required_for_activation: bool = Field(
        description="Whether this evidence item must be complete before live retrieval activation."
    )
    notes: str = Field(description="Human-readable explanation of the evidence requirement.")


class RetrievalEvidenceReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval evidence readiness view.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    evidence_ready: bool = Field(
        description="Whether retrieval evidence posture is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of retrieval evidence items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required retrieval evidence items currently marked complete."
    )
    items: list[RetrievalEvidenceReadinessItem] = Field(
        description="Governed retrieval evidence-readiness items."
    )
    approval_gate: EvaluationApprovalGateSummaryDescriptor = Field(
        description="Runtime-backed approval evidence summary for the retrieval rollout domain."
    )


class RetrievalGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval governance status view.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    governance_ready: bool = Field(
        description="Whether retrieval governance posture is currently sufficient for live activation."
    )
    activation_readiness: RetrievalActivationReadinessResponse = Field(
        description="Technical activation-readiness summary for retrieval execution."
    )
    runbook_readiness: RetrievalRunbookReadinessResponse = Field(
        description="Operational runbook-readiness summary for retrieval execution."
    )
    evidence_readiness: RetrievalEvidenceReadinessResponse = Field(
        description="Evaluation and citation evidence-readiness summary for retrieval execution."
    )
    blocking_area_count: int = Field(
        description="Number of top-level retrieval governance areas currently blocking activation."
    )
    governance_summary: list[str] = Field(
        description="Human-readable summary of the current retrieval governance posture."
    )
