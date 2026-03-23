from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.contracts.audit import AuditRecordResponse
from app.contracts.evidence import ExecutionEvidenceBundle
from app.contracts.safety import RedactionPosture, SafetyExecutionOutcome
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.db.models import AuditRecordModel
from app.services.safety_runtime import build_safety_execution_outcome_from_record


class SqlAlchemyAuditRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def save(self, record: AuditRecordResponse) -> None:
        model = AuditRecordModel(
            request_id=record.request_id,
            execution_status=record.execution_status.value,
            task_id=record.task_id,
            category=record.category.value,
            output_label=record.output_label.value,
            caller_app=record.caller_app,
            correlation_id=record.correlation_id,
            requested_by=record.requested_by,
            tenant_id=record.tenant_id,
            prompt_version=record.prompt_version,
            provider_mode=record.provider_mode,
            safety_mode=record.safety_mode,
            redaction_posture=record.redaction_posture.value,
            enforced_safety_controls=record.enforced_safety_controls,
            safety_outcome_payload=record.safety_outcome.model_dump(mode="json"),
            generated_at=record.generated_at,
            stubbed=record.stubbed,
            context_summary=record.context_summary,
            context_keys=record.context_keys,
            source_refs=record.source_refs,
            result_preview=record.result_preview,
            structured_output=record.structured_output,
            evidence=record.evidence.model_dump(mode="json"),
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

    def list(
        self,
        *,
        caller_app: str | None = None,
        task_id: str | None = None,
        category: str | None = None,
        output_label: str | None = None,
        requested_by: str | None = None,
        tenant_id: str | None = None,
        limit: int = 20,
    ) -> list[AuditRecordResponse]:
        statement = (
            select(AuditRecordModel).order_by(AuditRecordModel.generated_at.desc()).limit(limit)
        )
        if caller_app is not None:
            statement = statement.where(AuditRecordModel.caller_app == caller_app)
        if task_id is not None:
            statement = statement.where(AuditRecordModel.task_id == task_id)
        if category is not None:
            statement = statement.where(AuditRecordModel.category == category)
        if output_label is not None:
            statement = statement.where(AuditRecordModel.output_label == output_label)
        if requested_by is not None:
            statement = statement.where(AuditRecordModel.requested_by == requested_by)
        if tenant_id is not None:
            statement = statement.where(AuditRecordModel.tenant_id == tenant_id)
        with self._session_factory() as session:
            models = session.execute(statement).scalars().all()
            return [self._to_contract(model) for model in models]

    def _to_contract(self, model: AuditRecordModel) -> AuditRecordResponse:
        output_label = OutputLabel(model.output_label)
        redaction_posture = RedactionPosture(model.redaction_posture)
        safety_outcome = (
            SafetyExecutionOutcome.model_validate(model.safety_outcome_payload)
            if model.safety_outcome_payload is not None
            else build_safety_execution_outcome_from_record(
                safety_mode=model.safety_mode,
                output_label=output_label,
                redaction_posture=redaction_posture,
                enforced_controls=model.enforced_safety_controls,
            )
        )
        return AuditRecordResponse(
            request_id=model.request_id,
            execution_status=TaskExecutionStatus(model.execution_status),
            task_id=model.task_id,
            category=TaskCategory(model.category),
            output_label=output_label,
            caller_app=model.caller_app,
            correlation_id=model.correlation_id,
            requested_by=model.requested_by,
            tenant_id=model.tenant_id,
            prompt_version=model.prompt_version,
            provider_mode=model.provider_mode,
            safety_mode=model.safety_mode,
            redaction_posture=redaction_posture,
            enforced_safety_controls=model.enforced_safety_controls,
            safety_outcome=safety_outcome,
            generated_at=model.generated_at,
            stubbed=model.stubbed,
            context_summary=model.context_summary,
            context_keys=model.context_keys,
            source_refs=model.source_refs,
            result_preview=model.result_preview,
            structured_output=model.structured_output,
            evidence=ExecutionEvidenceBundle.model_validate(model.evidence),
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
