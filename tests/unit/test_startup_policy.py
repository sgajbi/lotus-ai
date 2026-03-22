from app.config import settings
from app.main import app, health_ready
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


def test_health_ready_degrades_when_probe_policy_requires_it() -> None:
    settings.readiness_probe_policy = "degrade"
    app.state.startup_readiness_findings = ["retrieval store: missing tables"]
    import anyio
    from fastapi import Response

    response = Response()
    result = anyio.run(health_ready, response)

    assert response.status_code == 503
    assert result["status"] == "degraded"

    settings.readiness_probe_policy = "observe"
    app.state.startup_readiness_findings = []
