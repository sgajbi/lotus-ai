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
    assert detail_response.json()["registration"]["activation_state"] == "PAUSED"
