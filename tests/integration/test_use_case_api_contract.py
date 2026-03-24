from fastapi.testclient import TestClient


def test_first_production_use_case_route(client: TestClient) -> None:
    response = client.get("/platform/use-cases/first-production-use-case")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["downstream_app"] == "lotus-performance"
    assert body["capability_pack_id"] == "analytics_commentary.pack.v1"
    assert body["capability_pack_family_id"] == "analytics_commentary"
    assert body["task_id"] == "explain.v1"
    assert body["output_label"] == "EXPLANATION_ONLY"
    assert body["contract_hardened"] is True
    assert any(
        field["field_name"] == "metric_deltas" for field in body["downstream_contract_fields"]
    )


def test_first_production_use_case_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/use-cases/first-production-use-case/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["downstream_app"] == "lotus-performance"
    assert body["readiness_ready"] is False
    assert body["approval_gate"]["domain_id"] == "first_use_case_onboarding"
    assert body["approval_gate"]["evidence_state"] == "STAGED_ONLY"
    assert any(item["evidence_id"] == "lotus_performance_caller_policy" for item in body["items"])
    assert any(
        item["evidence_id"] == "lotus_performance_durable_audit_review" for item in body["items"]
    )


def test_first_production_use_case_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/use-cases/first-production-use-case/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["downstream_app"] == "lotus-performance"
    assert body["runbook_ready"] is True
    assert any(item["runbook_id"] == "lotus_performance_shared_ownership" for item in body["items"])


def test_first_production_use_case_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/use-cases/first-production-use-case/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["downstream_app"] == "lotus-performance"
    assert body["rollout_stage"] == "PRE_PROD_VALIDATION"
    assert body["operational_posture"] == "LIMITED_ROLLOUT_BLOCKED"
    assert body["active_production_ready"] is False
    assert body["governance_ready"] is False
    assert body["readiness"]["approval_gate"]["domain_id"] == "first_use_case_onboarding"
    assert body["runbook_readiness"]["runbook_ready"] is True


def test_use_case_onboarding_template_route(client: TestClient) -> None:
    response = client.get("/platform/use-cases/onboarding-template")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["template_id"] == "bounded_explanation_only_onboarding.v1"
    assert body["based_on_use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["based_on_capability_pack_id"] == "analytics_commentary.pack.v1"
    assert any(item["checklist_id"] == "contract_boundary_defined" for item in body["checklist"])
    assert any(
        item["criterion_id"] == "approval_governance_summary" for item in body["approval_criteria"]
    )
