from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditRecordModel(Base):
    __tablename__ = "audit_records"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    output_label: Mapped[str] = mapped_column(String(64), nullable=False)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    safety_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    redaction_posture: Mapped[str] = mapped_column(String(64), nullable=False)
    enforced_safety_controls: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    stubbed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    context_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    result_preview: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class RetrievalSourceModel(Base):
    __tablename__ = "retrieval_sources"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    documents: Mapped[list["RetrievalDocumentModel"]] = relationship(back_populates="source")
    index_jobs: Mapped[list["RetrievalIndexJobModel"]] = relationship(back_populates="source")


class RetrievalDocumentModel(Base):
    __tablename__ = "retrieval_documents"

    document_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    promotion_status: Mapped[str] = mapped_column(String(64), nullable=False)
    index_status: Mapped[str] = mapped_column(String(64), nullable=False)

    source: Mapped["RetrievalSourceModel"] = relationship(back_populates="documents")
    chunks: Mapped[list["RetrievalChunkModel"]] = relationship(back_populates="document")


class RetrievalChunkModel(Base):
    __tablename__ = "retrieval_chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_documents.document_id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped["RetrievalDocumentModel"] = relationship(back_populates="chunks")
    embeddings: Mapped[list["RetrievalChunkEmbeddingModel"]] = relationship(back_populates="chunk")


class RetrievalChunkEmbeddingModel(Base):
    __tablename__ = "retrieval_chunk_embeddings"

    embedding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_chunks.chunk_id"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_documents.document_id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_status: Mapped[str] = mapped_column(String(64), nullable=False)
    vector_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)

    chunk: Mapped["RetrievalChunkModel"] = relationship(back_populates="embeddings")


class RetrievalIndexJobModel(Base):
    __tablename__ = "retrieval_index_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped["RetrievalSourceModel"] = relationship(back_populates="index_jobs")
    events: Mapped[list["RetrievalIndexJobEventModel"]] = relationship(back_populates="job")


class RetrievalIndexJobEventModel(Base):
    __tablename__ = "retrieval_index_job_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_index_jobs.job_id"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["RetrievalIndexJobModel"] = relationship(back_populates="events")


class PromptDefinitionModel(Base):
    __tablename__ = "prompt_definitions"

    task_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    management_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    output_contract_notes: Mapped[str] = mapped_column(Text, nullable=False)
