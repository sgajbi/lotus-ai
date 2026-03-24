from pathlib import Path

from app.config import settings
from app.services.access_control_runtime import (
    build_access_control_runtime_status,
    list_caller_policies,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_access_control_runtime_status_reports_enforced_memory_mode() -> None:
    settings.access_control_store_mode = "memory"
    settings.database_url = None

    status = build_access_control_runtime_status()

    assert status.store_mode == "memory"
    assert status.enforcement_state.value == "ENFORCED"
    assert status.store.status.value == "READY"
    assert status.policy_count >= 4
    assert status.tenant_isolation_active is True


def test_access_control_runtime_status_reports_enforced_sql_policy_resolution(tmp_path: Path) -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'access-control-runtime.db'}"
    upgrade_database_to_head(settings.database_url)

    status = build_access_control_runtime_status()

    assert status.store_mode == "sqlalchemy"
    assert status.enforcement_state.value == "ENFORCED"
    assert status.store.status.value == "READY"
    assert "restart-safe" in status.status_summary[1]


def test_list_caller_policies_returns_catalog() -> None:
    catalog = list_caller_policies()

    assert catalog.policy_count >= 4
    assert any(policy.caller_app == "lotus-platform" for policy in catalog.policies)
