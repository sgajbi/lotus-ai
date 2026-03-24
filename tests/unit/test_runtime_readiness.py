from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.runtime_readiness import (
    get_access_control_store_runtime_status,
    get_audit_store_runtime_status,
    get_retrieval_store_runtime_status,
)


def test_audit_store_runtime_status_defaults_to_ready_memory_mode() -> None:
    settings.audit_store_mode = "memory"
    settings.database_url = None

    status_descriptor = get_audit_store_runtime_status()

    assert status_descriptor.mode == "memory"
    assert status_descriptor.status == RuntimeReadinessStatus.READY


def test_retrieval_store_runtime_status_requires_database_for_sqlalchemy_mode() -> None:
    settings.retrieval_store_mode = "sqlalchemy"
    settings.database_url = None

    status_descriptor = get_retrieval_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.CONFIGURATION_REQUIRED

    settings.retrieval_store_mode = "memory"


def test_audit_store_runtime_status_reports_migration_required_for_unmigrated_database(
    tmp_path: Path,
) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'unmigrated-audit.db'}"

    status_descriptor = get_audit_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.MIGRATION_REQUIRED
    assert "missing required tables" in status_descriptor.detail

    settings.audit_store_mode = "memory"
    settings.database_url = None


def test_retrieval_store_runtime_status_reports_unsupported_mode() -> None:
    settings.retrieval_store_mode = "unsupported"
    settings.database_url = None

    status_descriptor = get_retrieval_store_runtime_status()

    assert status_descriptor.mode == "unsupported"
    assert status_descriptor.status == RuntimeReadinessStatus.UNAVAILABLE
    assert "not supported" in status_descriptor.detail

    settings.retrieval_store_mode = "memory"


def test_audit_store_runtime_status_reports_unsupported_mode() -> None:
    settings.audit_store_mode = "unsupported"
    settings.database_url = None

    status_descriptor = get_audit_store_runtime_status()

    assert status_descriptor.mode == "unsupported"
    assert status_descriptor.status == RuntimeReadinessStatus.UNAVAILABLE
    assert "not supported" in status_descriptor.detail

    settings.audit_store_mode = "memory"


def test_retrieval_store_runtime_status_reports_database_unavailable() -> None:
    settings.retrieval_store_mode = "sqlalchemy"
    settings.database_url = "sqlite:///ignored.db"
    failing_engine = MagicMock()
    failing_engine.connect.side_effect = SQLAlchemyError("unavailable")

    with patch("app.services.runtime_readiness.create_engine", return_value=failing_engine):
        status_descriptor = get_retrieval_store_runtime_status()

    assert status_descriptor.status == RuntimeReadinessStatus.UNAVAILABLE
    assert "Database connectivity check failed" in status_descriptor.detail

    settings.retrieval_store_mode = "memory"
    settings.database_url = None


def test_access_control_store_runtime_status_requires_database_for_sqlalchemy_mode() -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = None

    status_descriptor = get_access_control_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.CONFIGURATION_REQUIRED


def test_access_control_store_runtime_status_reports_migration_required_for_unmigrated_database(
    tmp_path: Path,
) -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'unmigrated-access-control.db'}"

    status_descriptor = get_access_control_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.MIGRATION_REQUIRED
    assert "caller_policies" in status_descriptor.detail


def test_access_control_store_runtime_status_reports_unsupported_mode() -> None:
    settings.access_control_store_mode = "unsupported"
    settings.database_url = None

    status_descriptor = get_access_control_store_runtime_status()

    assert status_descriptor.mode == "unsupported"
    assert status_descriptor.status == RuntimeReadinessStatus.UNAVAILABLE
    assert "not supported" in status_descriptor.detail
