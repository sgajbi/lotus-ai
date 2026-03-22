from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditRecordModel(Base):
    __tablename__ = "audit_records"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    stubbed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    context_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    result_preview: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


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
    preview: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped["RetrievalDocumentModel"] = relationship(back_populates="chunks")


class RetrievalIndexJobModel(Base):
    __tablename__ = "retrieval_index_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped["RetrievalSourceModel"] = relationship(back_populates="index_jobs")


class PromptDefinitionModel(Base):
    __tablename__ = "prompt_definitions"

    task_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    output_contract_notes: Mapped[str] = mapped_column(Text, nullable=False)
