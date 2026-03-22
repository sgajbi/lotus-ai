from app.config import settings
from app.services.startup_policy import evaluate_startup_readiness


def test_startup_readiness_warn_policy_records_non_ready_sql_store_without_blocking() -> None:
    settings.audit_store_mode = "memory"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.database_url = None
    settings.startup_readiness_policy = "warn"

    evaluation = evaluate_startup_readiness()

    assert evaluation.blocking is False
    assert any("retrieval store:" in finding for finding in evaluation.findings)

    settings.retrieval_store_mode = "memory"
    settings.startup_readiness_policy = "warn"


def test_startup_readiness_enforce_policy_blocks_non_ready_sql_store() -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "memory"
    settings.database_url = None
    settings.startup_readiness_policy = "enforce"

    evaluation = evaluate_startup_readiness()

    assert evaluation.blocking is True
    assert any("audit store:" in finding for finding in evaluation.findings)

    settings.audit_store_mode = "memory"
    settings.startup_readiness_policy = "warn"
