from pathlib import Path

from app.config import settings
from app.services.access_control_governance import build_access_control_governance_status
from tests.support.migration_runner import upgrade_database_to_head


def test_access_control_governance_status_blocks_when_store_is_memory() -> None:
    settings.access_control_store_mode = "memory"
    settings.database_url = None

    status = build_access_control_governance_status()

    assert status.governance_ready is False
    assert status.enforcement_state.value == "FULLY_ENFORCED"
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is True
    assert status.blocking_area_count == 1


def test_access_control_governance_status_reports_sql_backed_registry_ready(tmp_path: Path) -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'access-control-governance.db'}"
    upgrade_database_to_head(settings.database_url)

    status = build_access_control_governance_status()

    assert status.governance_ready is True
    assert status.enforcement_state.value == "FULLY_ENFORCED"
    assert status.activation_readiness.activation_ready is True
    assert status.runbook_readiness.runbook_ready is True
    assert status.tenant_restricted_policy_count >= 2
    assert status.blocking_area_count == 0
