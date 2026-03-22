from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalIndexJobEventDescriptor,
    RetrievalIndexJobEventStatus,
    RetrievalIndexJobRefreshDescriptor,
    RetrievalIndexJobRefreshStatus,
    RetrievalPipelineStage,
)
from app.retrieval.foundation_embedding import build_preview_embedding

PREVIEW_EMBEDDING_MODEL = "foundation.text-embedding-preview"


@dataclass(frozen=True)
class IndexedChunkRefreshRecord:
    chunk: RetrievalChunkDescriptor
    embedding_id: str
    embedding_model: str
    vector_dimensions: int
    embedding_vector: list[float]
    content_checksum: str


def build_indexed_chunk_refresh_record(
    *,
    document: RetrievalDocumentDescriptor,
    chunk: RetrievalChunkDescriptor,
) -> IndexedChunkRefreshRecord:
    embedding_vector = build_preview_embedding(f"{document.title} {chunk.preview}")
    return IndexedChunkRefreshRecord(
        chunk=chunk,
        embedding_id=build_embedding_id(chunk.chunk_id),
        embedding_model=PREVIEW_EMBEDDING_MODEL,
        vector_dimensions=len(embedding_vector),
        embedding_vector=embedding_vector,
        content_checksum=chunk.content_checksum,
    )


def build_embedding_id(chunk_id: str) -> str:
    return f"emb_{chunk_id}"


def build_refresh_event(
    *,
    job_id: str,
    ordinal: int,
    status: RetrievalIndexJobRefreshStatus,
    notes: str,
) -> RetrievalIndexJobEventDescriptor:
    return RetrievalIndexJobEventDescriptor(
        event_id=f"evt_{job_id}_refresh_{ordinal:04d}",
        job_id=job_id,
        stage=RetrievalPipelineStage.ENABLED,
        status=(
            RetrievalIndexJobEventStatus.COMPLETED
            if status == RetrievalIndexJobRefreshStatus.COMPLETED
            else RetrievalIndexJobEventStatus.FAILED
        ),
        recorded_at=_utc_now_iso(),
        notes=notes,
    )


def build_refresh_descriptor(
    *,
    status: RetrievalIndexJobRefreshStatus,
    refreshed_document_count: int,
    refreshed_chunk_count: int,
    persisted_embedding_count: int,
    replayed_embedding_count: int,
    message: str,
    event: RetrievalIndexJobEventDescriptor,
) -> RetrievalIndexJobRefreshDescriptor:
    return RetrievalIndexJobRefreshDescriptor(
        status=status,
        refreshed_document_count=refreshed_document_count,
        refreshed_chunk_count=refreshed_chunk_count,
        persisted_embedding_count=persisted_embedding_count,
        replayed_embedding_count=replayed_embedding_count,
        message=message,
        event=event,
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
