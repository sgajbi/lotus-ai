from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentDescriptor,
    RetrievalDocumentGovernanceDescriptor,
    RetrievalDocumentGovernanceResponse,
    RetrievalDocumentPromotionStatus,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository


def build_retrieval_document_governance() -> RetrievalDocumentGovernanceResponse:
    repository = get_retrieval_repository()
    documents = [
        document
        for source in repository.list_sources()
        for document in repository.list_documents_for_source(source.source_id)
    ]
    governance_documents = [
        _build_document_governance_descriptor(document=document) for document in documents
    ]
    searchable_document_count = sum(
        1 for document in governance_documents if document.search_enabled
    )
    return RetrievalDocumentGovernanceResponse(
        service=settings.service_name,
        retrieval_mode=settings.retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        document_count=len(governance_documents),
        searchable_document_count=searchable_document_count,
        staged_document_count=len(governance_documents) - searchable_document_count,
        documents=governance_documents,
    )


def _build_document_governance_descriptor(
    *, document: RetrievalDocumentDescriptor
) -> RetrievalDocumentGovernanceDescriptor:
    search_enabled = document.promotion_status == RetrievalDocumentPromotionStatus.SEARCHABLE
    notes = (
        "Promoted into bounded retrieval scope for current foundation-phase execution."
        if search_enabled
        else "Staged for retrieval governance, but not yet promoted into searchable scope."
    )
    return RetrievalDocumentGovernanceDescriptor(
        document_id=document.document_id,
        source_id=document.source_id,
        title=document.title,
        promotion_status=document.promotion_status,
        search_enabled=search_enabled,
        chunk_count=document.chunk_count,
        index_status=document.index_status,
        notes=notes,
    )
