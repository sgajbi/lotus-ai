from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.retrieval import (
    RetrievalChunkCatalogResponse,
    RetrievalDocumentCatalogResponse,
    RetrievalDocumentGovernanceResponse,
    RetrievalIndexJobCatalogResponse,
    RetrievalIndexJobDetailResponse,
    RetrievalIndexStatusResponse,
    RetrievalIndexingPolicyResponse,
    RetrievalSourceGovernanceResponse,
    RetrievalRuntimeStatusResponse,
)
from app.retrieval.document_governance import build_retrieval_document_governance
from app.retrieval.document_registry import (
    build_retrieval_index_status,
    list_chunks_for_document,
    list_documents_for_source,
)
from app.retrieval.job_registry import (
    build_retrieval_indexing_policy,
    build_retrieval_runtime_status,
    build_retrieval_job_catalog,
    get_retrieval_job_detail,
)
from app.retrieval.source_governance import build_retrieval_source_governance
from app.retrieval.source_registry import list_retrieval_sources


def get_retrieval_index_status() -> RetrievalIndexStatusResponse:
    return build_retrieval_index_status()


def get_documents_for_source(source_id: str) -> RetrievalDocumentCatalogResponse:
    source_catalog = list_retrieval_sources()
    if not any(source.source_id == source_id for source in source_catalog.sources):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown retrieval source_id: {source_id}",
        )
    return list_documents_for_source(source_id)


def get_chunks_for_document(document_id: str) -> RetrievalChunkCatalogResponse:
    chunks = list_chunks_for_document(document_id)
    if chunks is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown retrieval document_id: {document_id}",
        )
    return chunks


def get_retrieval_job_catalog() -> RetrievalIndexJobCatalogResponse:
    return build_retrieval_job_catalog()


def get_retrieval_job_detail_or_raise(job_id: str) -> RetrievalIndexJobDetailResponse:
    return get_retrieval_job_detail(job_id)


def get_retrieval_indexing_policy() -> RetrievalIndexingPolicyResponse:
    return build_retrieval_indexing_policy()


def get_retrieval_runtime_status() -> RetrievalRuntimeStatusResponse:
    return build_retrieval_runtime_status()


def get_retrieval_source_governance() -> RetrievalSourceGovernanceResponse:
    return build_retrieval_source_governance()


def get_retrieval_document_governance() -> RetrievalDocumentGovernanceResponse:
    return build_retrieval_document_governance()
