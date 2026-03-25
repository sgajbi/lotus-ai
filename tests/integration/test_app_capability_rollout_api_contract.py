from fastapi.testclient import TestClient


def test_app_capability_rollout_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/app-capability-rollouts")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["pairing_count"] == 4
    assert body["onboarded_pairing_count"] == 1
    assert body["active_pairing_count"] == 0
    assert body["downstream_app_count"] == 4
    assert body["rollout_records"][0]["downstream_app"] == "lotus-performance"
    assert body["rollout_records"][0]["capability_pack_id"] == "analytics_commentary.pack.v1"
    assert body["rollout_records"][0]["capability_pack_maturity_stage"] == "REUSABLE"
    assert body["rollout_records"][0]["rollout_stage"] == "INTEGRATION_IN_PROGRESS"


def test_app_capability_rollout_detail_and_governance_routes(client: TestClient) -> None:
    detail_response = client.get(
        "/platform/app-capability-rollouts/lotus-performance/analytics_commentary.pack.v1"
    )
    governance_response = client.get(
        "/platform/app-capability-rollouts/lotus-performance/analytics_commentary.pack.v1/governance-status"
    )
    catalog_governance_response = client.get("/platform/app-capability-rollouts/governance-status")

    assert detail_response.status_code == 200
    assert governance_response.status_code == 200
    assert catalog_governance_response.status_code == 200
    assert detail_response.json()["record"]["downstream_app"] == "lotus-performance"
    assert any(
        boundary["owner"] == "lotus-performance"
        for boundary in detail_response.json()["ownership_boundaries"]
    )
    assert governance_response.json()["governance_ready"] is True
    assert governance_response.json()["blocking_area_count"] == 0
    assert catalog_governance_response.json()["ready_pairing_count"] == 1
    assert catalog_governance_response.json()["blocking_pairing_count"] == 3


def test_app_capability_rollout_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/app-capability-rollouts/observability-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["pairing_count"] == 4
    assert body["active_pairing_count"] == 0
    assert body["blocked_pairing_count"] == 4
    assert body["observability_ready"] is True
    assert body["items"][0]["downstream_app"] == "lotus-performance"
    assert body["items"][0]["estate_visibility_state"] == "BLOCKED"
    assert "/platform/observability/incident-summary" in body["items"][0]["linked_endpoints"]


def test_app_capability_rollout_lifecycle_routes(client: TestClient) -> None:
    catalog_response = client.get("/platform/app-capability-rollouts/lifecycle-status")
    detail_response = client.get(
        "/platform/app-capability-rollouts/lotus-performance/analytics_commentary.pack.v1/lifecycle-status"
    )

    assert catalog_response.status_code == 200
    assert detail_response.status_code == 200
    assert catalog_response.json()["ready_pairing_count"] == 1
    assert catalog_response.json()["blocking_pairing_count"] == 3
    assert detail_response.json()["record"]["downstream_app"] == "lotus-performance"
    assert detail_response.json()["lifecycle_ready"] is True
    assert detail_response.json()["retirement_ready_now"] is True
    assert detail_response.json()["retirement_scope"] == "PAIRING_WITH_GLOBAL_PACK_REVIEW"
    assert len(detail_response.json()["retirement_rationale_summary"]) == 2
    assert any(
        item["item_id"] == "historical_traceability_surface"
        for item in detail_response.json()["items"]
    )


def test_app_capability_onboarding_template_route(client: TestClient) -> None:
    response = client.get(
        "/platform/app-capability-rollouts/lotus-performance/analytics_commentary.pack.v1/onboarding-template"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["downstream_app"] == "lotus-performance"
    assert body["capability_pack_id"] == "analytics_commentary.pack.v1"
    assert body["based_on_pack_template_id"] == "analytics_commentary.pack.v1.adoption-template.v1"
    assert body["reference_use_case_template_id"] == "bounded_explanation_only_onboarding.v1"
    assert any(
        item["checklist_id"] == "runtime_eval_family_staged_and_passing"
        for item in body["checklist"]
    )


def test_app_capability_rollout_detail_route_rejects_unknown_pairing(client: TestClient) -> None:
    response = client.get("/platform/app-capability-rollouts/unknown/unknown.pack.v1")

    assert response.status_code == 404
    assert "Unknown app-capability rollout" in response.json()["detail"]


def test_app_capability_rollout_pairing_routes_reject_unknown_pairing(client: TestClient) -> None:
    paths = [
        "/platform/app-capability-rollouts/unknown/unknown.pack.v1/governance-status",
        "/platform/app-capability-rollouts/unknown/unknown.pack.v1/lifecycle-status",
        "/platform/app-capability-rollouts/unknown/unknown.pack.v1/onboarding-template",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 404
        assert "Unknown app-capability rollout" in response.json()["detail"]
