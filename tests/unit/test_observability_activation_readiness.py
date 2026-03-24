from pathlib import Path

from app.config import settings
from app.services.observability_activation_readiness import (
    build_observability_activation_readiness,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_observability_activation_readiness_blocks_without_durable_stores() -> None:
    settings.audit_store_mode = "memory"
    settings.access_control_store_mode = "memory"
    settings.database_url = None

    readiness = build_observability_activation_readiness()

    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 2
    assert "SQL-backed audit storage" in readiness.blocking_findings[0]
    assert "SQL-backed caller-policy storage" in readiness.blocking_findings[1]


def test_observability_activation_readiness_reports_sql_backed_posture_ready(
    tmp_path: Path,
) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'observability-activation.db'}"
    upgrade_database_to_head(settings.database_url)

    readiness = build_observability_activation_readiness()

    assert readiness.activation_ready is True
    assert readiness.domain_count == 6
    assert readiness.blocking_findings == []
