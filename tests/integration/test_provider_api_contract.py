from fastapi.testclient import TestClient


def test_provider_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["text_generation_configuration"]["rollout_state"] == "STUB_DEFAULT"
    assert body["text_generation_configuration"]["credential_status"] == "NOT_CONFIGURED"
    assert body["runtime_execution_enabled"] is False
    assert any(provider["provider_id"] == "text.stub" for provider in body["providers"])
    assert any(
        provider["provider_id"] == "text.live_documented"
        and provider["adapter_kind"] == "DOCUMENTED_LIVE"
        and provider["failure_category_on_use"] == "LIVE_EXECUTION_NOT_ENABLED"
        for provider in body["providers"]
    )


def test_provider_policy_route(client: TestClient) -> None:
    response = client.get("/platform/providers/policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["text_generation_configuration"]["rollout_state"] == "STUB_DEFAULT"
    text_policy = next(
        policy for policy in body["policies"] if policy["capability"] == "TEXT_GENERATION"
    )
    assert text_policy["selected_adapter_kind"] == "STUB"
    assert text_policy["rejection_category"] == "UNSUPPORTED_MODE"


def test_provider_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["text_generation_configuration"]["rollout_state"] == "STUB_DEFAULT"
    assert body["text_generation_configuration"]["credential_status"] == "NOT_CONFIGURED"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 5
    assert len(body["activation_path"]) == 5


def test_provider_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "provider_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


def test_provider_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 6
    assert body["completed_required_item_count"] == 4
    assert body["items"][0]["evidence_id"] == "provider_policy_fixture_pack"
    assert body["items"][0]["status"] == "READY"
    assert body["items"][1]["evidence_id"] == "provider_runtime_fixture_pack"
    assert body["items"][1]["status"] == "READY"
    assert body["items"][3]["evidence_id"] == "provider_regression_run_baseline"
    assert body["items"][3]["status"] == "READY"
    assert body["items"][4]["status"] == "FOUNDATION_STAGED"


def test_provider_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/providers/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 3
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert body["evidence_readiness"]["evidence_ready"] is False
    assert len(body["governance_summary"]) == 3
