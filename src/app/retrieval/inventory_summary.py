from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import RetrievalIndexStatus
from app.services.retrieval_store import get_retrieval_repository


@dataclass(frozen=True)
class RetrievalSourceInventorySummary:
    source_id: str
    document_count: int
    chunk_count: int
    index_status: RetrievalIndexStatus


@dataclass(frozen=True)
class RetrievalRuntimeInventorySummary:
    source_count: int
    document_count: int
    chunk_count: int
    index_job_count: int


def summarize_retrieval_source_inventory(source_id: str) -> RetrievalSourceInventorySummary:
    repository = get_retrieval_repository()
    documents = repository.list_documents_for_source(source_id)
    chunk_count = sum(
        len(repository.list_chunks_for_document(document.document_id)) for document in documents
    )
    if not documents:
        index_status = RetrievalIndexStatus.NOT_INDEXED
    elif all(document.index_status == RetrievalIndexStatus.INDEXED for document in documents):
        index_status = RetrievalIndexStatus.INDEXED
    else:
        index_status = RetrievalIndexStatus.STAGED
    return RetrievalSourceInventorySummary(
        source_id=source_id,
        document_count=len(documents),
        chunk_count=chunk_count,
        index_status=index_status,
    )


def summarize_retrieval_runtime_inventory() -> RetrievalRuntimeInventorySummary:
    repository = get_retrieval_repository()
    sources = repository.list_sources()
    documents = [
        document
        for source in sources
        for document in repository.list_documents_for_source(source.source_id)
    ]
    chunk_count = sum(
        len(repository.list_chunks_for_document(document.document_id)) for document in documents
    )
    jobs = repository.list_index_jobs()
    return RetrievalRuntimeInventorySummary(
        source_count=len(sources),
        document_count=len(documents),
        chunk_count=chunk_count,
        index_job_count=len(jobs),
    )
