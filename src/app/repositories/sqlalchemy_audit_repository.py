from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.contracts.audit import AuditRecordResponse
from app.contracts.safety import RedactionPosture
from app.db.models import AuditRecordModel


class SqlAlchemyAuditRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def save(self, record: AuditRecordResponse) -> None:
        model = AuditRecordModel(
            request_id=record.request_id,
            task_id=record.task_id,
            caller_app=record.caller_app,
            correlation_id=record.correlation_id,
            prompt_version=record.prompt_version,
            provider_mode=record.provider_mode,
            safety_mode=record.safety_mode,
            redaction_posture=record.redaction_posture.value,
            enforced_safety_controls=record.enforced_safety_controls,
            generated_at=record.generated_at,
            stubbed=record.stubbed,
            context_summary=record.context_summary,
            context_keys=record.context_keys,
            source_refs=record.source_refs,
            result_preview=record.result_preview,
            structured_output=record.structured_output,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def get(self, request_id: str) -> AuditRecordResponse | None:
        with self._session_factory() as session:
            model = session.get(AuditRecordModel, request_id)
            if model is None:
                return None
            return self._to_contract(model)

    def _to_contract(self, model: AuditRecordModel) -> AuditRecordResponse:
        return AuditRecordResponse(
            request_id=model.request_id,
            task_id=model.task_id,
            caller_app=model.caller_app,
            correlation_id=model.correlation_id,
            prompt_version=model.prompt_version,
            provider_mode=model.provider_mode,
            safety_mode=model.safety_mode,
            redaction_posture=RedactionPosture(model.redaction_posture),
            enforced_safety_controls=model.enforced_safety_controls,
            generated_at=model.generated_at,
            stubbed=model.stubbed,
            context_summary=model.context_summary,
            context_keys=model.context_keys,
            source_refs=model.source_refs,
            result_preview=model.result_preview,
            structured_output=model.structured_output,
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        db_path = self._database_url.removeprefix(prefix)
        if db_path == ":memory:":
            return
        path = Path(db_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
