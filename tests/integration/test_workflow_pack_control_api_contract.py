from fastapi.testclient import TestClient

from app.main import app
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_workflow_pack_control_history_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/control-history")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert "PAUSE" in body["supported_action_types"]


def test_workflow_pack_control_action_route(client: TestClient) -> None:
    response = client.post(
        "/platform/workflow-packs/control-actions",
        json={
            "pack_id": "advisor_brief.pack",
            "version": "v1",
            "action_type": "PAUSE",
            "caller_app": "lotus-platform",
            "requested_by": "operator-route",
            "approved_by": "approver-route",
            "reason": "Pause via API contract test.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["action_type"] == "PAUSE"
    assert body["registration"]["activation_state"] == "PAUSED"
    assert body["event"]["authorization"]["caller_app"] == "lotus-platform"
    assert body["event"]["authorization"]["outcome"] == "ALLOWED"


def test_workflow_pack_control_action_route_blocks_non_operator_caller(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/control-actions",
        json={
            "pack_id": "advisor_brief.pack",
            "version": "v1",
            "action_type": "DEPRECATE",
            "caller_app": "lotus-manage",
            "requested_by": "operator-route",
            "approved_by": "approver-route",
            "reason": "Non-operator caller should be blocked.",
        },
    )

    assert response.status_code == 403
    assert "not authorized for async control-plane actions" in response.json()["detail"]


def test_workflow_pack_control_history_and_registration_state_support_sqlalchemy_store(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-control-store.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        workflow_pack_registry_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        durable_client = TestClient(app)
        try:
            pause_response = durable_client.post(
                "/platform/workflow-packs/control-actions",
                json={
                    "pack_id": "advisor_brief.pack",
                    "version": "v1",
                    "action_type": "PAUSE",
                    "caller_app": "lotus-platform",
                    "requested_by": "operator-route",
                    "approved_by": "approver-route",
                    "reason": "Pause via durable API contract test.",
                },
            )
            history_response = durable_client.get("/platform/workflow-packs/control-history")
            detail_response = durable_client.get(
                "/platform/workflow-packs/registry/advisor_brief.pack/v1"
            )
        finally:
            durable_client.close()

    assert pause_response.status_code == 200
    assert history_response.status_code == 200
    assert detail_response.status_code == 200
    assert history_response.json()["control_plane_store_mode"] == "sqlalchemy"
    assert history_response.json()["latest_events"][0]["action_type"] == "PAUSE"
    assert (
        history_response.json()["latest_events"][0]["authorization"]["caller_app"]
        == "lotus-platform"
    )
    assert history_response.json()["latest_events"][0]["authorization"]["outcome"] == "ALLOWED"
    assert detail_response.json()["registration"]["activation_state"] == "PAUSED"


def test_workflow_pack_control_routes_degrade_when_sql_store_is_unmigrated(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-control-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_registry_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            history_response = durable_client.get("/platform/workflow-packs/control-history")
            action_response = durable_client.post(
                "/platform/workflow-packs/control-actions",
                json={
                    "pack_id": "advisor_brief.pack",
                    "version": "v1",
                    "action_type": "PAUSE",
                    "caller_app": "lotus-platform",
                    "requested_by": "operator-route",
                    "approved_by": "approver-route",
                    "reason": "Should degrade when registry store is unmigrated.",
                },
            )

    assert history_response.status_code == 503
    assert action_response.status_code == 503
    assert "Workflow-pack registry store is not ready." in history_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in history_response.json()["detail"]
    assert "Workflow-pack registry store is not ready." in action_response.json()["detail"]
