from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RetrievalSourceKind(str, Enum):
    RFC = "RFC"
    STANDARD = "STANDARD"
    ARCHITECTURE = "ARCHITECTURE"
    OPENAPI = "OPENAPI"


class RetrievalStatus(str, Enum):
    DISABLED = "DISABLED"
    READY = "READY"


class RetrievalSourceDescriptor(BaseModel):
    source_id: str = Field(description="Stable retrieval source identifier.")
    kind: RetrievalSourceKind = Field(description="High-level source category.")
    enabled: bool = Field(description="Whether the source is currently enabled for search.")
    description: str = Field(description="Human-readable source description.")


class RetrievalSourceCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the retrieval source catalog.")
    retrieval_mode: str = Field(description="Current retrieval mode configured for lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    sources: list[RetrievalSourceDescriptor] = Field(
        description="Approved retrieval source descriptors known to lotus-ai."
    )


class RetrievalSearchRequest(BaseModel):
    query: str = Field(description="Search query provided by the caller.")
    caller_app: str = Field(description="Calling Lotus application requesting retrieval.")
    correlation_id: str = Field(description="Correlation identifier for the retrieval request.")
    source_ids: list[str] = Field(
        default_factory=list,
        description="Optional source filters limiting retrieval to approved source ids.",
    )
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of hits requested.")


class RetrievalSearchHit(BaseModel):
    source_id: str = Field(description="Retrieval source identifier that produced the hit.")
    score: float = Field(description="Relevance score associated with the hit.")
    snippet: str = Field(description="Short snippet preview for the hit.")


class RetrievalSearchResponse(BaseModel):
    status: RetrievalStatus = Field(description="Current retrieval execution status.")
    query: str = Field(description="Original caller query.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    hits: list[RetrievalSearchHit] = Field(description="Retrieval hits returned by the search.")
    message: str = Field(description="Human-readable retrieval status message.")
