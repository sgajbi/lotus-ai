from fastapi.testclient import TestClient


def test_prompt_registry_routes(client: TestClient) -> None:
    list_response = client.get("/platform/prompts")
    assert list_response.status_code == 200
    assert any(prompt["task_id"] == "explain.v1" for prompt in list_response.json())
    assert all(prompt["lifecycle_status"] == "ACTIVE" for prompt in list_response.json())

    detail_response = client.get("/platform/prompts/explain.v1")
    assert detail_response.status_code == 200
    assert detail_response.json()["prompt_version"] == "foundation.explain.v1"
    assert detail_response.json()["management_mode"] == "SEEDED_MEMORY"


def test_prompt_governance_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/governance")

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_store_mode"] == "memory"
    assert body["management_mode"] == "SEEDED_MEMORY"
    assert body["runtime_mutation_enabled"] is False
    assert body["promotion_write_api_enabled"] is False
    assert "durable and explicit" in body["promotion_path"]
    assert body["active_prompt_count"] >= 7


def test_prompt_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["prompt_store_mode"] == "memory"
    assert body["selection_mode"] == "STATIC_ACTIVE"
    assert body["rollout_mode"] == "GOVERNED_STATE_READ_ONLY"
    assert body["candidate_prompt_count"] == 0
    assert any(selection["task_id"] == "explain.v1" for selection in body["selections"])
    assert body["selections"][0]["rollout_role"] == "ACTIVE"
    assert any(state["task_id"] == "explain.v1" for state in body["rollout_states"])


def test_prompt_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["prompt_store_mode"] == "memory"
    assert body["management_mode"] == "SEEDED_MEMORY"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 4


def test_prompt_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "prompt_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


def test_prompt_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["evidence_id"] == "prompt_fixture_coverage_pack"
    assert body["items"][1]["status"] == "NOT_READY"


def test_prompt_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/prompts/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 3
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert body["evidence_readiness"]["evidence_ready"] is False
    assert len(body["governance_summary"]) == 3
