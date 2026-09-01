from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.db.models import (
    ProviderBudgetStateModel,
    ProviderDegradationStateModel,
    ProviderOperationsEventModel,
    ProviderQuotaStateModel,
)
from app.services.runtime_readiness import (
    get_access_control_store_runtime_status,
    get_audit_store_runtime_status,
    get_provider_operations_store_runtime_status,
    get_retrieval_store_runtime_status,
    get_workflow_pack_registry_store_runtime_status,
    get_workflow_pack_task_flow_store_runtime_status,
)
from tests.support.migration_runner import upgrade_database_to_head


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


def test_workflow_pack_registry_store_runtime_status_requires_database_for_sqlalchemy_mode() -> (
    None
):
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.database_url = None

    status_descriptor = get_workflow_pack_registry_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.CONFIGURATION_REQUIRED


def test_workflow_pack_registry_store_runtime_status_reports_migration_required_for_unmigrated_database(
    tmp_path: Path,
) -> None:
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'unmigrated-workflow-pack-registry.db'}"

    status_descriptor = get_workflow_pack_registry_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.MIGRATION_REQUIRED
    assert "workflow_pack_registrations" in status_descriptor.detail


def test_workflow_pack_registry_store_runtime_status_reports_unsupported_mode() -> None:
    settings.workflow_pack_registry_store_mode = "unsupported"
    settings.database_url = None

    status_descriptor = get_workflow_pack_registry_store_runtime_status()

    assert status_descriptor.mode == "unsupported"
    assert status_descriptor.status == RuntimeReadinessStatus.UNAVAILABLE
    assert "not supported" in status_descriptor.detail


def test_workflow_pack_task_flow_store_runtime_status_requires_database_for_sqlalchemy_mode() -> (
    None
):
    settings.workflow_pack_task_flow_store_mode = "sqlalchemy"
    settings.database_url = None

    status_descriptor = get_workflow_pack_task_flow_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.CONFIGURATION_REQUIRED


def test_workflow_pack_task_flow_store_runtime_status_reports_migration_required_for_unmigrated_database(
    tmp_path: Path,
) -> None:
    settings.workflow_pack_task_flow_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'unmigrated-workflow-pack-task-flow.db'}"

    status_descriptor = get_workflow_pack_task_flow_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.MIGRATION_REQUIRED
    assert "workflow_pack_task_flows" in status_descriptor.detail


def test_workflow_pack_task_flow_store_runtime_status_reports_unsupported_mode() -> None:
    settings.workflow_pack_task_flow_store_mode = "unsupported"
    settings.database_url = None

    status_descriptor = get_workflow_pack_task_flow_store_runtime_status()

    assert status_descriptor.mode == "unsupported"
    assert status_descriptor.status == RuntimeReadinessStatus.UNAVAILABLE
    assert "not supported" in status_descriptor.detail


def test_a_migrated_database_reports_every_store_ready(tmp_path: Path) -> None:
    """Probes are measured, not declared.

    The provider-operations probe expected a table named
    "provider_operations_state" that no migration has ever created, so it
    reported MIGRATION_REQUIRED on every correctly migrated database - and
    every test of its consumers (production baseline, resilience runtime)
    monkeypatches it, so the real probe was never once run against a real
    schema. This test runs them all for real.
    """

    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-readiness.db'}"
    upgrade_database_to_head(settings.database_url)
    for mode_attribute in (
        "audit_store_mode",
        "retrieval_store_mode",
        "access_control_store_mode",
        "workflow_pack_registry_store_mode",
        "workflow_pack_task_flow_store_mode",
        "provider_operations_store_mode",
    ):
        setattr(settings, mode_attribute, "sqlalchemy")

    for name, descriptor in (
        ("audit", get_audit_store_runtime_status()),
        ("retrieval", get_retrieval_store_runtime_status()),
        ("access control", get_access_control_store_runtime_status()),
        ("workflow-pack registry", get_workflow_pack_registry_store_runtime_status()),
        ("workflow-pack task flow", get_workflow_pack_task_flow_store_runtime_status()),
        ("provider operations", get_provider_operations_store_runtime_status()),
    ):
        assert descriptor.status == RuntimeReadinessStatus.READY, (
            f"{name} store probe reports {descriptor.status} on a fully migrated "
            f"database: {descriptor.detail}"
        )


def test_the_provider_operations_probe_names_the_tables_the_repository_uses() -> None:
    """The probe's table list is a claim about the repository's storage; the
    repository's own models are the authority. Keeping them tied here is what
    stops the list drifting into naming a table nobody writes."""

    repository_tables = {
        model.__tablename__
        for model in (
            ProviderBudgetStateModel,
            ProviderDegradationStateModel,
            ProviderOperationsEventModel,
            ProviderQuotaStateModel,
        )
    }
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = None

    descriptor = get_provider_operations_store_runtime_status()
    assert descriptor.status == RuntimeReadinessStatus.CONFIGURATION_REQUIRED

    with patch("app.services.runtime_readiness._probe_sql_tables") as probe:
        probe.return_value = (RuntimeReadinessStatus.READY, "probed")
        get_provider_operations_store_runtime_status()
    assert set(probe.call_args.args[0]) == repository_tables
