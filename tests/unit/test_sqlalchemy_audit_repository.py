from pathlib import Path

from app.contracts.audit import AuditRecordResponse
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.safety import RedactionPosture
from app.contracts.tasks import OutputLabel, TaskCategory
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_audit_repository_save_and_get(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    record = AuditRecordResponse(
        request_id="air_sql_1",
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
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
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )

    repository.save(record)

    loaded = repository.get("air_sql_1")
    assert loaded == record
    assert repository.get("air_missing") is None


def test_sqlalchemy_audit_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-audit.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyAuditRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_audit_repository_list_filters_and_orders_latest_first(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-list.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    old_record = AuditRecordResponse(
        request_id="air_sql_old",
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-sql-old",
        prompt_version="foundation.explain.v1",
        provider_mode="disabled",
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Old",
        context_keys=["status"],
        source_refs=[],
        result_preview="Old",
        structured_output={},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )
    new_record = old_record.model_copy(
        update={
            "request_id": "air_sql_new",
            "task_id": "summarize.v1",
            "category": TaskCategory.SUMMARIZE,
            "output_label": OutputLabel.DRAFT,
            "caller_app": "lotus-advise",
            "generated_at": "2026-03-22T01:00:00Z",
        }
    )

    repository.save(old_record)
    repository.save(new_record)

    all_records = repository.list()
    advise_records = repository.list(caller_app="lotus-advise", limit=10)

    assert [record.request_id for record in all_records] == ["air_sql_new", "air_sql_old"]
    assert [record.request_id for record in advise_records] == ["air_sql_new"]
