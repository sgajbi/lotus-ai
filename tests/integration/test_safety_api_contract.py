from fastapi.testclient import TestClient


def test_safety_policy_route(client: TestClient) -> None:
    response = client.get("/platform/safety/policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["safety_mode"] == "documented_only"
    assert any(control["control_id"] == "response_labeling" for control in body["controls"])
    assert any(task["task_id"] == "explain.v1" for task in body["task_policies"])


def test_safety_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/safety/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["safety_mode"] == "documented_only"
    assert body["runtime_redaction_active"] is False
    assert body["enforced_control_ids"] == ["response_labeling", "correlation_and_audit"]
