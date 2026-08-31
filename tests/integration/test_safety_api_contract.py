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
    assert body["runtime_redaction_active"] is True
    assert body["runtime_redaction_disposition"] == "ENFORCED_PASSTHROUGH"
    assert body["enforced_control_ids"] == [
        "response_labeling",
        "correlation_and_audit",
        "runtime_redaction_engine",
    ]
    assert body["supported_execution_dispositions"] == ["DOCUMENTED_ONLY"]


def test_safety_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/safety/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["approval_gate"]["domain_id"] == "safety_enforcement"
    assert body["approval_gate"]["evidence_state"] == "STAGED_ONLY"


def test_safety_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/safety/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "safety_operational_runbook"


def test_safety_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/safety/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["runtime_status"]["runtime_redaction_active"] is True
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert body["evidence_readiness"]["approval_gate"]["domain_id"] == "safety_enforcement"
