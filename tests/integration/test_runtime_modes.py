from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_sql_backed_runtime_status_is_ready_after_migration(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'runtime-ready.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        audit_store_mode="sqlalchemy",
        retrieval_store_mode="sqlalchemy",
        workflow_pack_registry_store_mode="sqlalchemy",
        workflow_pack_run_store_mode="sqlalchemy",
        database_url=database_url,
        startup_readiness_policy="enforce",
        readiness_probe_policy="degrade",
    ):
        with TestClient(app) as client:
            platform_status = client.get("/platform/runtime-status")
            retrieval_status = client.get("/platform/retrieval/runtime-status")
            ready_status = client.get("/health/ready")

    assert platform_status.status_code == 200
    platform_body = platform_status.json()
    assert platform_body["audit_store"]["status"] == "READY"
    assert platform_body["retrieval_store"]["status"] == "READY"
    assert platform_body["workflow_pack_registry_store"]["status"] == "READY"
    assert platform_body["workflow_pack_run_store"]["status"] == "READY"
    assert platform_body["startup_readiness_blocking"] is False

    assert retrieval_status.status_code == 200
    retrieval_body = retrieval_status.json()
    assert retrieval_body["retrieval_store_status"] == "READY"

    assert ready_status.status_code == 200
    assert ready_status.json()["status"] == "ready"


def test_health_ready_degrades_for_unmigrated_sql_retrieval_store(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'runtime-unmigrated.db'}"

    with override_runtime_settings(
        audit_store_mode="memory",
        retrieval_store_mode="sqlalchemy",
        database_url=database_url,
        startup_readiness_policy="warn",
        readiness_probe_policy="degrade",
    ):
        with TestClient(app) as client:
            ready_status = client.get("/health/ready")
            platform_status = client.get("/platform/runtime-status")
            retrieval_status = client.get("/platform/retrieval/runtime-status")

    assert ready_status.status_code == 503
    assert ready_status.json()["status"] == "degraded"

    platform_body = platform_status.json()
    assert platform_body["startup_readiness_blocking"] is False
    assert any(
        "retrieval store:" in warning for warning in platform_body["startup_readiness_warnings"]
    )
    assert platform_body["retrieval_store"]["status"] == "MIGRATION_REQUIRED"

    retrieval_body = retrieval_status.json()
    assert retrieval_body["retrieval_store_status"] == "MIGRATION_REQUIRED"


def test_health_ready_degrades_for_unmigrated_sql_workflow_pack_run_store(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-runtime-unmigrated.db'}"

    with override_runtime_settings(
        audit_store_mode="memory",
        retrieval_store_mode="memory",
        workflow_pack_run_store_mode="sqlalchemy",
        database_url=database_url,
        startup_readiness_policy="warn",
        readiness_probe_policy="degrade",
    ):
        with TestClient(app) as client:
            ready_status = client.get("/health/ready")
            platform_status = client.get("/platform/runtime-status")

    assert ready_status.status_code == 503
    assert ready_status.json()["status"] == "degraded"

    platform_body = platform_status.json()
    assert platform_body["startup_readiness_blocking"] is False
    assert any(
        "workflow-pack run store:" in warning
        for warning in platform_body["startup_readiness_warnings"]
    )
    assert platform_body["workflow_pack_run_store"]["status"] == "MIGRATION_REQUIRED"


def test_health_ready_degrades_for_unmigrated_sql_workflow_pack_registry_store(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-registry-unmigrated.db'}"

    with override_runtime_settings(
        audit_store_mode="memory",
        retrieval_store_mode="memory",
        workflow_pack_registry_store_mode="sqlalchemy",
        database_url=database_url,
        startup_readiness_policy="warn",
        readiness_probe_policy="degrade",
    ):
        with TestClient(app) as client:
            ready_status = client.get("/health/ready")
            platform_status = client.get("/platform/runtime-status")

    assert ready_status.status_code == 503
    assert ready_status.json()["status"] == "degraded"

    platform_body = platform_status.json()
    assert any(
        "workflow-pack registry store:" in warning
        for warning in platform_body["startup_readiness_warnings"]
    )
    assert platform_body["workflow_pack_registry_store"]["status"] == "MIGRATION_REQUIRED"


def test_startup_enforce_policy_blocks_unmigrated_sql_store(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'runtime-blocked.db'}"

    with override_runtime_settings(
        audit_store_mode="sqlalchemy",
        retrieval_store_mode="memory",
        database_url=database_url,
        startup_readiness_policy="enforce",
        readiness_probe_policy="observe",
    ):
        with pytest.raises(RuntimeError, match="startup readiness policy blocked startup"):
            with TestClient(app):
                pass


def test_health_ready_returns_draining_when_service_is_marked_draining() -> None:
    with override_runtime_settings(
        startup_readiness_policy="warn",
        readiness_probe_policy="observe",
    ):
        with TestClient(app) as client:
            app.state.is_draining = True
            ready_status = client.get("/health/ready")
            app.state.is_draining = False

    assert ready_status.status_code == 503
    assert ready_status.json()["status"] == "draining"
