from pathlib import Path

from app.contracts.audit import AuditRecordResponse
from app.contracts.safety import RedactionPosture
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_audit_repository_save_and_get(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    record = AuditRecordResponse(
        request_id="air_sql_1",
        task_id="explain.v1",
        caller_app="lotus-manage",
        correlation_id="corr-sql-1",
        prompt_version="foundation.explain.v1",
        provider_mode="disabled",
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Explain rebalance outcome",
        context_keys=["status"],
        source_refs=["lotus-manage:run:reb_sql_1"],
        result_preview="Stub execution completed.",
        structured_output={"phase": "foundation"},
    )

    repository.save(record)

    loaded = repository.get("air_sql_1")
    assert loaded == record
    assert repository.get("air_missing") is None
