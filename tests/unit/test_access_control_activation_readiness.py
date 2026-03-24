from pathlib import Path

from app.config import settings
from app.services.access_control_activation_readiness import (
    build_access_control_activation_readiness,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_access_control_activation_readiness_blocks_memory_mode() -> None:
    settings.access_control_store_mode = "memory"
    settings.database_url = None

    status = build_access_control_activation_readiness()

    assert status.activation_ready is False
    assert status.enforcement_state.value == "FULLY_ENFORCED"
    assert len(status.blocking_findings) == 1


def test_access_control_activation_readiness_reports_sql_ready(tmp_path: Path) -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'access-control-activation.db'}"
    upgrade_database_to_head(settings.database_url)

    status = build_access_control_activation_readiness()

    assert status.activation_ready is True
    assert status.store_mode == "sqlalchemy"
    assert status.blocking_findings == []
