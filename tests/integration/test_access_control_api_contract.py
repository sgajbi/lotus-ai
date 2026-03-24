from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_access_control_routes_report_memory_posture(client: TestClient) -> None:
    runtime_response = client.get("/platform/access-control/runtime-status")
    assert runtime_response.status_code == 200
    runtime_body = runtime_response.json()
    assert runtime_body["store_mode"] == "memory"
    assert runtime_body["enforcement_state"] == "FULLY_ENFORCED"
    assert runtime_body["data_plane_enforced"] is True
    assert runtime_body["control_plane_enforced"] is True
    assert runtime_body["tenant_isolation_active"] is True
    assert runtime_body["policy_count"] >= 5

    activation_response = client.get("/platform/access-control/activation-readiness")
    assert activation_response.status_code == 200
    activation_body = activation_response.json()
    assert activation_body["activation_ready"] is False
    assert activation_body["enforcement_state"] == "FULLY_ENFORCED"

    runbook_response = client.get("/platform/access-control/runbook-readiness")
    assert runbook_response.status_code == 200
    runbook_body = runbook_response.json()
    assert runbook_body["runbook_ready"] is True
    assert runbook_body["required_item_count"] == 5

    governance_response = client.get("/platform/access-control/governance-status")
    assert governance_response.status_code == 200
    governance_body = governance_response.json()
    assert governance_body["governance_ready"] is False
    assert governance_body["activation_readiness"]["activation_ready"] is False
    assert governance_body["runbook_readiness"]["runbook_ready"] is True
    assert governance_body["blocking_area_count"] == 1

    catalog_response = client.get("/platform/access-control/caller-policies")
    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["store_mode"] == "memory"
    assert any(policy["caller_app"] == "lotus-platform" for policy in catalog_body["policies"])


def test_access_control_routes_report_sql_backed_registry(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'access-control-api.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        access_control_store_mode="sqlalchemy", database_url=database_url
    ):
        with TestClient(app) as durable_client:
            runtime_response = durable_client.get("/platform/access-control/runtime-status")
            assert runtime_response.status_code == 200
            runtime_body = runtime_response.json()
            assert runtime_body["store_mode"] == "sqlalchemy"
            assert runtime_body["store"]["status"] == "READY"
            assert runtime_body["enforcement_state"] == "FULLY_ENFORCED"

            activation_response = durable_client.get(
                "/platform/access-control/activation-readiness"
            )
            assert activation_response.status_code == 200
            assert activation_response.json()["activation_ready"] is True

            governance_response = durable_client.get("/platform/access-control/governance-status")
            assert governance_response.status_code == 200
            governance_body = governance_response.json()
            assert governance_body["governance_ready"] is True
            assert governance_body["activation_readiness"]["activation_ready"] is True
            assert governance_body["runbook_readiness"]["runbook_ready"] is True
            assert governance_body["blocking_area_count"] == 0
