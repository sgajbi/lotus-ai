from __future__ import annotations

from app.contracts.retrieval import (
    RetrievalSourceCatalogResponse,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.config import settings

VECTOR_STORE_STRATEGY = "postgresql+pgvector"

_SOURCES: list[RetrievalSourceDescriptor] = [
    RetrievalSourceDescriptor(
        source_id="lotus-platform-rfcs",
        kind=RetrievalSourceKind.RFC,
        enabled=False,
        description="Approved Lotus platform RFC documents.",
    ),
    RetrievalSourceDescriptor(
        source_id="lotus-platform-standards",
        kind=RetrievalSourceKind.STANDARD,
        enabled=False,
        description="Approved Lotus standards and governance documents.",
    ),
    RetrievalSourceDescriptor(
        source_id="lotus-ai-architecture",
        kind=RetrievalSourceKind.ARCHITECTURE,
        enabled=False,
        description="lotus-ai architecture, guides, and service-local design documentation.",
    ),
    RetrievalSourceDescriptor(
        source_id="lotus-openapi-derived",
        kind=RetrievalSourceKind.OPENAPI,
        enabled=False,
        description="OpenAPI-derived documentation and approved schema references.",
    ),
]


def list_retrieval_sources() -> RetrievalSourceCatalogResponse:
    return RetrievalSourceCatalogResponse(
        service=settings.service_name,
        retrieval_mode=settings.retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        sources=_SOURCES,
    )
