from pathlib import Path

from app.config import settings
from app.services.observability_governance import build_observability_governance_status
from tests.support.migration_runner import upgrade_database_to_head


def test_observability_governance_blocks_when_supporting_stores_are_memory() -> None:
    settings.audit_store_mode = "memory"
    settings.access_control_store_mode = "memory"
    settings.database_url = None

    status = build_observability_governance_status()

    assert status.governance_ready is False
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is True
    assert status.blocking_area_count == 1


def test_observability_governance_reports_sql_backed_posture_ready(tmp_path: Path) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'observability-governance.db'}"
    upgrade_database_to_head(settings.database_url)

    status = build_observability_governance_status()

    assert status.governance_ready is True
    assert status.activation_readiness.activation_ready is True
    assert status.runbook_readiness.runbook_ready is True
    assert status.blocking_area_count == 0
