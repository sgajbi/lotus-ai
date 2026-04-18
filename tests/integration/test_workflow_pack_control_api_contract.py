from fastapi.testclient import TestClient


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
