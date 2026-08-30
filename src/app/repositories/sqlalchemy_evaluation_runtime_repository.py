from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db.models import EvaluationCaseResultModel, EvaluationRunAttemptModel, EvaluationRunModel
from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
    EvaluationRuntimeRepository,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyEvaluationRuntimeRepository(SqlAlchemyRepositoryBase, EvaluationRuntimeRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_runs(self) -> list[EvaluationRunRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(EvaluationRunModel).order_by(EvaluationRunModel.submitted_at)
            ).all()
            return [self._to_run_record(model) for model in models]

    def get_run(self, *, run_id: str) -> EvaluationRunRecord | None:
        with self._session_factory() as session:
            model = session.get(EvaluationRunModel, run_id)
            if model is None:
                return None
            return self._to_run_record(model)

    def save_run(self, record: EvaluationRunRecord) -> None:
        model = EvaluationRunModel(
            run_id=record.run_id,
            fixture_id=record.fixture_id,
            manifest_version=record.manifest_version,
            lifecycle_status=record.lifecycle_status,
            triggered_by=record.triggered_by,
            submitted_at=record.submitted_at,
            async_job_id=record.async_job_id,
            latest_message=record.latest_message,
            verdict=record.verdict,
            case_count=record.case_count,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def list_attempts(self, *, run_id: str) -> list[EvaluationRunAttemptRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(EvaluationRunAttemptModel)
                .where(EvaluationRunAttemptModel.run_id == run_id)
                .order_by(EvaluationRunAttemptModel.attempt_number)
            ).all()
            return [self._to_attempt_record(model) for model in models]

    def save_attempt(self, record: EvaluationRunAttemptRecord) -> None:
        model = EvaluationRunAttemptModel(
            attempt_id=record.attempt_id,
            run_id=record.run_id,
            attempt_number=record.attempt_number,
            lifecycle_status=record.lifecycle_status,
            started_at=record.started_at,
            completed_at=record.completed_at,
            worker_id=record.worker_id,
            latest_message=record.latest_message,
            verdict=record.verdict,
            failure_reason=record.failure_reason,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def get_attempt(self, *, attempt_id: str) -> EvaluationRunAttemptRecord | None:
        with self._session_factory() as session:
            model = session.get(EvaluationRunAttemptModel, attempt_id)
            if model is None:
                return None
            return self._to_attempt_record(model)

    def list_case_results(self, *, run_id: str) -> list[EvaluationCaseResultRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(EvaluationCaseResultModel)
                .where(EvaluationCaseResultModel.run_id == run_id)
                .order_by(EvaluationCaseResultModel.case_result_id)
            ).all()
            return [self._to_case_result_record(model) for model in models]

    def save_case_result(self, record: EvaluationCaseResultRecord) -> None:
        model = EvaluationCaseResultModel(
            case_result_id=record.case_result_id,
            run_id=record.run_id,
            attempt_id=record.attempt_id,
            case_id=record.case_id,
            fixture_id=record.fixture_id,
            outcome=record.outcome,
            summary=record.summary,
            evidence_refs=record.evidence_refs,
            artifact_ids=record.artifact_ids,
            provider_config_sha256=record.provider_config_sha256,
            recorded_at=record.recorded_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _to_run_record(self, model: EvaluationRunModel) -> EvaluationRunRecord:
        return EvaluationRunRecord(
            run_id=model.run_id,
            fixture_id=model.fixture_id,
            manifest_version=model.manifest_version,
            lifecycle_status=model.lifecycle_status,
            triggered_by=model.triggered_by,
            submitted_at=model.submitted_at,
            async_job_id=model.async_job_id,
            latest_message=model.latest_message,
            verdict=model.verdict,
            case_count=model.case_count,
        )

    def _to_attempt_record(self, model: EvaluationRunAttemptModel) -> EvaluationRunAttemptRecord:
        return EvaluationRunAttemptRecord(
            attempt_id=model.attempt_id,
            run_id=model.run_id,
            attempt_number=model.attempt_number,
            lifecycle_status=model.lifecycle_status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            worker_id=model.worker_id,
            latest_message=model.latest_message,
            verdict=model.verdict,
            failure_reason=model.failure_reason,
        )

    def _to_case_result_record(
        self, model: EvaluationCaseResultModel
    ) -> EvaluationCaseResultRecord:
        return EvaluationCaseResultRecord(
            case_result_id=model.case_result_id,
            run_id=model.run_id,
            attempt_id=model.attempt_id,
            case_id=model.case_id,
            fixture_id=model.fixture_id,
            outcome=model.outcome,
            summary=model.summary,
            evidence_refs=list(model.evidence_refs),
            artifact_ids=list(model.artifact_ids),
            provider_config_sha256=model.provider_config_sha256,
            recorded_at=model.recorded_at,
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
