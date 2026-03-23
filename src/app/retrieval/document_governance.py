from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentGovernanceDescriptor,
    RetrievalDocumentGovernanceResponse,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.retrieval.search_eligibility import build_document_eligibility
from app.services.retrieval_store import get_retrieval_repository


def build_retrieval_document_governance() -> RetrievalDocumentGovernanceResponse:
    repository = get_retrieval_repository()
    documents: list[RetrievalDocumentGovernanceDescriptor] = []
    for source in repository.list_sources():
        for document in repository.list_documents_for_source(source.source_id):
            eligibility = build_document_eligibility(source=source, document=document)
            documents.append(
                RetrievalDocumentGovernanceDescriptor(
                    document_id=document.document_id,
                    source_id=document.source_id,
                    title=document.title,
                    governance_status=eligibility.governance_status,
                    search_enabled=eligibility.search_enabled,
                    chunk_count=document.chunk_count,
                    index_status=document.index_status,
                    notes=eligibility.notes,
                )
            )

    documents.sort(key=lambda item: (item.source_id, item.document_id))
    return RetrievalDocumentGovernanceResponse(
        service=settings.service_name,
        retrieval_mode=settings.retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        searchable_document_count=sum(1 for document in documents if document.search_enabled),
        index_pending_document_count=sum(
            1 for document in documents if document.governance_status == "INDEX_PENDING"
        ),
        blocked_document_count=sum(
            1 for document in documents if document.governance_status == "BLOCKED_BY_SOURCE"
        ),
        documents=documents,
    )
