from __future__ import annotations

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
