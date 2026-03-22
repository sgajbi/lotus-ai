from __future__ import annotations

from app.contracts.retrieval import (
    RetrievalIndexJobEventDescriptor,
    RetrievalIndexJobEventStatus,
    RetrievalIndexJobStepDescriptor,
    RetrievalPipelineStage,
)


def build_default_index_job_steps(*, job_id: str) -> list[RetrievalIndexJobStepDescriptor]:
    return [
        RetrievalIndexJobStepDescriptor(
            step_id=f"{job_id}.source_curation",
            name="Source curation",
            stage=RetrievalPipelineStage.STAGED,
            description=(
                "Approved source inventory is explicitly curated before indexing is enabled."
            ),
        ),
        RetrievalIndexJobStepDescriptor(
            step_id=f"{job_id}.document_inventory",
            name="Document inventory",
            stage=RetrievalPipelineStage.STAGED,
            description=(
                "Documents, promoted scope, and chunk checksums are recorded for deterministic replay."
            ),
        ),
        RetrievalIndexJobStepDescriptor(
            step_id=f"{job_id}.embedding_generation",
            name="Embedding generation",
            stage=RetrievalPipelineStage.STAGED,
            description=(
                "Durable embedding records are now staged in persistence, but live generation remains disabled."
            ),
        ),
        RetrievalIndexJobStepDescriptor(
            step_id=f"{job_id}.vector_persistence",
            name="Vector persistence",
            stage=RetrievalPipelineStage.DOCUMENTED,
            description=(
                "Durable vector persistence will use PostgreSQL with pgvector when enabled."
            ),
        ),
    ]


def build_default_index_job_events(*, job_id: str) -> list[RetrievalIndexJobEventDescriptor]:
    return [
        RetrievalIndexJobEventDescriptor(
            event_id=f"{job_id}.source_curation.default",
            job_id=job_id,
            stage=RetrievalPipelineStage.STAGED,
            status=RetrievalIndexJobEventStatus.STAGED,
            recorded_at="2026-03-22T00:00:00Z",
            notes="No persisted indexing lifecycle events are recorded yet for this job.",
        )
    ]
