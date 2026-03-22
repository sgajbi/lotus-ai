from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import RetrievalDocumentPromotionStatus, RetrievalIndexStatus
from app.services.retrieval_store import get_retrieval_repository


@dataclass(frozen=True)
class RetrievalSourceInventorySummary:
    source_id: str
    document_count: int
    searchable_document_count: int
    staged_document_count: int
    chunk_count: int
    embedding_record_count: int
    index_status: RetrievalIndexStatus


@dataclass(frozen=True)
class RetrievalRuntimeInventorySummary:
    source_count: int
    document_count: int
    searchable_document_count: int
    staged_document_count: int
    chunk_count: int
    embedding_record_count: int
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
    searchable_document_count = sum(
        1
        for document in documents
        if document.promotion_status == RetrievalDocumentPromotionStatus.SEARCHABLE
    )
    return RetrievalSourceInventorySummary(
        source_id=source_id,
        document_count=len(documents),
        searchable_document_count=searchable_document_count,
        staged_document_count=len(documents) - searchable_document_count,
        chunk_count=chunk_count,
        embedding_record_count=repository.count_embedding_records_for_source(source_id),
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
        searchable_document_count=sum(
            1
            for document in documents
            if document.promotion_status == RetrievalDocumentPromotionStatus.SEARCHABLE
        ),
        staged_document_count=sum(
            1
            for document in documents
            if document.promotion_status == RetrievalDocumentPromotionStatus.STAGED
        ),
        chunk_count=chunk_count,
        embedding_record_count=repository.count_embedding_records(),
        index_job_count=len(jobs),
    )
