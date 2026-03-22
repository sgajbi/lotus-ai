from __future__ import annotations

from typing import Protocol

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalSourceDescriptor,
)


class RetrievalRepository(Protocol):
    def list_sources(self) -> list[RetrievalSourceDescriptor]: ...

    def list_source_ids(self) -> list[str]: ...

    def get_source(self, source_id: str) -> RetrievalSourceDescriptor | None: ...

    def list_documents_for_source(self, source_id: str) -> list[RetrievalDocumentDescriptor]: ...

    def get_document(self, document_id: str) -> RetrievalDocumentDescriptor | None: ...

    def list_chunks_for_document(self, document_id: str) -> list[RetrievalChunkDescriptor]: ...
