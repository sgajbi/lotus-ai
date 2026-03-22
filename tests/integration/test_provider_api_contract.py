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
        provider["provider_id"] == "text.openai"
        and provider["adapter_kind"] == "OPENAI_LIVE"
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
    assert text_policy["allowed_modes"] == ["disabled", "stub", "openai"]


def test_provider_quota_policy_route(client: TestClient) -> None:
    response = client.get("/platform/providers/quota-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["quota_enforced"] is False
    assert body["configuration_valid"] is True
    assert body["matching_order"] == ["TENANT", "CALLER_APP", "TASK", "DEFAULT"]
    assert body["quotas"] == []


def test_provider_budget_policy_route(client: TestClient) -> None:
    response = client.get("/platform/providers/budget-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["budget_enforced"] is False
    assert body["configuration_valid"] is True
    assert body["budget_state"] == "NOT_ENFORCED"
    assert body["current_spend_usd"] == 0.0
    assert body["remaining_budget_usd"] is None


def test_provider_operations_status_route(client: TestClient) -> None:
    response = client.get("/platform/providers/operations-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["operations_state"] == "ROLLOUT_BLOCKED"
    assert body["runtime_execution_enabled"] is False
    assert body["rollout_blocked"] is True
    assert body["quota_policy"]["quota_enforced"] is False
    assert body["budget_policy"]["budget_enforced"] is False
    assert body["degradation_status"]["status"] == "DOCUMENTED_ONLY"
    assert len(body["summary"]) == 4
    assert "Current blocking or warning detail:" in body["summary"][-1]


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
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 8
    assert "/platform/providers/quota-policy" in body["activation_path"][1]
    assert "/platform/providers/budget-policy" in body["activation_path"][2]
    assert "/platform/providers/operations-status" in body["activation_path"][3]
    assert "/platform/providers/governance-status" in body["activation_path"][-1]


def test_provider_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 7
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "provider_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"
    assert body["items"][3]["runbook_id"] == "provider_spend_anomaly_response"
    assert body["items"][5]["runbook_id"] == "provider_degradation_and_circuit_response"


def test_provider_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/providers/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 8
    assert body["completed_required_item_count"] == 6
    assert body["items"][0]["evidence_id"] == "provider_policy_fixture_pack"
    assert body["items"][0]["status"] == "READY"
    assert body["items"][1]["evidence_id"] == "provider_runtime_fixture_pack"
    assert body["items"][1]["status"] == "READY"
    assert body["items"][3]["evidence_id"] == "provider_operations_fixture_pack"
    assert body["items"][3]["status"] == "READY"
    assert body["items"][4]["evidence_id"] == "provider_degradation_fixture_pack"
    assert body["items"][4]["status"] == "READY"
    assert body["items"][5]["evidence_id"] == "provider_regression_run_baseline"
    assert body["items"][5]["status"] == "READY"
    assert body["items"][6]["status"] == "FOUNDATION_STAGED"


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
