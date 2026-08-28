from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.workflow_pack_run_store import reset_workflow_pack_run_store_cache
from app.workflow_pack_execution_idempotency.store import (
    reset_workflow_pack_execution_idempotency_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.workflow_pack_fixtures import (
    advisory_copilot_workflow_pack_execution_request_json,
)


def test_sync_execution_api_replays_original_run_and_rejects_changed_input(
    client: TestClient,
) -> None:
    payload = _payload(
        idempotency_key="advisor-memo-api-001",
        correlation_id="corr-advisor-memo-api-001",
    )

    created = client.post("/platform/workflow-packs/execute", json=payload)
    replayed = client.post("/platform/workflow-packs/execute", json=payload)
    changed = client.post(
        "/platform/workflow-packs/execute",
        json=_payload(
            idempotency_key="advisor-memo-api-001",
            correlation_id="corr-advisor-memo-api-changed",
        ),
    )
    run_catalog = client.get(
        "/platform/workflow-packs/runs",
        params={"caller_app": "lotus-advise"},
    )

    assert created.status_code == 200
    assert replayed.status_code == 200
    created_body = created.json()
    replayed_body = replayed.json()
    assert created_body["idempotency"]["status"] == "CREATED"
    assert replayed_body["idempotency"]["status"] == "REPLAYED"
    assert replayed_body["idempotency"]["record_id"] == created_body["idempotency"]["record_id"]
    assert (
        replayed_body["execution"]["audit"]["request_id"]
        == (created_body["execution"]["audit"]["request_id"])
    )
    assert (
        replayed_body["workflow_pack_run"]["run_id"]
        == (created_body["workflow_pack_run"]["run_id"])
    )
    assert changed.status_code == 409
    assert "workflow_pack_execution_idempotency_conflict" in changed.json()["detail"]
    assert run_catalog.status_code == 200
    assert run_catalog.json()["run_count"] == 1


def test_sql_backed_sync_replay_survives_repository_reconstruction(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-sync-idempotency-api.sqlite3'}"
    upgrade_database_to_head(database_url)
    payload = _payload(
        idempotency_key="advisor-memo-api-sql-001",
        correlation_id="corr-advisor-memo-api-sql-001",
    )

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            created = durable_client.post("/platform/workflow-packs/execute", json=payload)
            reset_workflow_pack_execution_idempotency_store_cache()
            replayed = durable_client.post("/platform/workflow-packs/execute", json=payload)
            run_catalog = durable_client.get(
                "/platform/workflow-packs/runs",
                params={"caller_app": "lotus-advise"},
            )

    reset_workflow_pack_execution_idempotency_store_cache()
    reset_workflow_pack_run_store_cache()

    assert created.status_code == 200
    assert replayed.status_code == 200
    created_body = created.json()
    replayed_body = replayed.json()
    assert replayed_body["idempotency"]["status"] == "REPLAYED"
    assert (
        replayed_body["execution"]["audit"]["request_id"]
        == (created_body["execution"]["audit"]["request_id"])
    )
    assert (
        replayed_body["workflow_pack_run"]["run_id"]
        == (created_body["workflow_pack_run"]["run_id"])
    )
    assert run_catalog.status_code == 200
    assert run_catalog.json()["run_count"] == 1
    assert settings.workflow_pack_run_store_mode == "memory"


def _payload(*, idempotency_key: str, correlation_id: str) -> dict[str, object]:
    payload = advisory_copilot_workflow_pack_execution_request_json(
        correlation_id=correlation_id,
        tenant_id="tenant-sg-001",
    )
    payload["idempotency_key"] = idempotency_key
    return payload
