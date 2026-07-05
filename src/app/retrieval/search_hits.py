from __future__ import annotations

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalDocumentVersionDescriptor,
    RetrievalDocumentVersionLifecycleStatus,
    RetrievalSearchHit,
    RetrievalSourceDescriptor,
)


def build_retrieval_search_hit(
    *,
    source: RetrievalSourceDescriptor,
    document: RetrievalDocumentDescriptor,
    chunk: RetrievalChunkDescriptor,
    document_versions: list[RetrievalDocumentVersionDescriptor],
    score: float,
) -> RetrievalSearchHit:
    active_version = select_active_document_version(document_versions)
    active_version_id = None if active_version is None else active_version.version_id
    return RetrievalSearchHit(
        source_id=chunk.source_id,
        source_kind=source.kind,
        document_id=chunk.document_id,
        document_title=document.title,
        document_location=document.location,
        chunk_id=chunk.chunk_id,
        chunk_order=chunk.chunk_order,
        score=score,
        snippet=chunk.preview,
        active_version_id=active_version_id,
        active_version_lifecycle_status=(
            None if active_version is None else active_version.lifecycle_status
        ),
        active_version_created_at=None if active_version is None else active_version.created_at,
        citation_ref=build_citation_ref(
            source_id=chunk.source_id,
            document_id=chunk.document_id,
            active_version_id=active_version_id,
            chunk_id=chunk.chunk_id,
        ),
    )


def select_active_document_version(
    document_versions: list[RetrievalDocumentVersionDescriptor],
) -> RetrievalDocumentVersionDescriptor | None:
    return next(
        (
            version
            for version in sorted(
                document_versions,
                key=lambda item: (item.created_at, item.version_id),
                reverse=True,
            )
            if version.lifecycle_status == RetrievalDocumentVersionLifecycleStatus.ACTIVE
        ),
        None,
    )


def build_citation_ref(
    *,
    source_id: str,
    document_id: str,
    active_version_id: str | None,
    chunk_id: str,
) -> str:
    version_ref = active_version_id or "unversioned"
    return f"{source_id}/{document_id}@{version_ref}#{chunk_id}"
