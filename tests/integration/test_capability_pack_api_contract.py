from fastapi.testclient import TestClient


def test_capability_pack_detail_route_for_analytics_commentary(client: TestClient) -> None:
    response = client.get("/platform/capability-packs/analytics_commentary.pack.v1")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["pack"]["pack_id"] == "analytics_commentary.pack.v1"
    assert body["pack"]["family_id"] == "analytics_commentary"
    assert body["pack"]["family_kind"] == "COMMENTARY"
    assert body["pack"]["current_anchor_use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["pack"]["quality_gate_domain_id"] == "analytics_commentary_pack"
    assert body["pack"]["quality_evidence_state"] == "STAGED_ONLY"
    assert body["approval_gate"]["domain_id"] == "analytics_commentary_pack"
    assert any(
        expectation["expectation_id"] == "grounded_to_caller_facts"
        for expectation in body["quality_expectations"]
    )
    assert any(
        behavior["behavior_id"] == "missing_metric_deltas"
        for behavior in body["unsupported_input_behaviors"]
    )


def test_capability_pack_detail_route_for_decision_explanation(client: TestClient) -> None:
    response = client.get("/platform/capability-packs/decision_explanation.pack.v1")

    assert response.status_code == 200
    body = response.json()
    assert body["pack"]["family_kind"] == "EXPLANATION"
    assert body["pack"]["current_anchor_use_case_id"] is None
    assert body["approval_gate"]["domain_id"] == "decision_explanation_pack"
    assert any(
        expectation["expectation_id"] == "grounded_to_deterministic_state"
        for expectation in body["quality_expectations"]
    )


def test_capability_pack_detail_route_rejects_unknown_pack(client: TestClient) -> None:
    response = client.get("/platform/capability-packs/unknown.pack")

    assert response.status_code == 404
    assert "Unknown capability pack" in response.json()["detail"]


def test_capability_pack_governance_routes_for_analytics_commentary(client: TestClient) -> None:
    adoption_template_response = client.get(
        "/platform/capability-packs/analytics_commentary.pack.v1/adoption-template"
    )
    observability_response = client.get(
        "/platform/capability-packs/analytics_commentary.pack.v1/observability-summary"
    )
    activation_response = client.get(
        "/platform/capability-packs/analytics_commentary.pack.v1/activation-readiness"
    )
    runbook_response = client.get(
        "/platform/capability-packs/analytics_commentary.pack.v1/runbook-readiness"
    )
    governance_response = client.get(
        "/platform/capability-packs/analytics_commentary.pack.v1/governance-status"
    )
    catalog_governance_response = client.get("/platform/capability-packs/governance-status")

    assert adoption_template_response.status_code == 200
    assert observability_response.status_code == 200
    assert activation_response.status_code == 200
    assert runbook_response.status_code == 200
    assert governance_response.status_code == 200
    assert catalog_governance_response.status_code == 200
    assert adoption_template_response.json()["pack_id"] == "analytics_commentary.pack.v1"
    assert adoption_template_response.json()["current_reference_use_case_id"] == (
        "lotus_performance.analytics_commentary.v1"
    )
    assert observability_response.json()["pack_id"] == "analytics_commentary.pack.v1"
    assert activation_response.json()["pack_id"] == "analytics_commentary.pack.v1"
    assert runbook_response.json()["pack_id"] == "analytics_commentary.pack.v1"
    assert governance_response.json()["pack_id"] == "analytics_commentary.pack.v1"
    assert "pack_summaries" in catalog_governance_response.json()


def test_capability_pack_adoption_template_route_for_decision_explanation(
    client: TestClient,
) -> None:
    response = client.get(
        "/platform/capability-packs/decision_explanation.pack.v1/adoption-template"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pack_id"] == "decision_explanation.pack.v1"
    assert body["current_reference_use_case_id"] is None
    assert any(
        item["checklist_id"] == "deterministic_decision_owner_defined" for item in body["checklist"]
    )


def test_capability_pack_governance_routes_reject_unknown_pack(client: TestClient) -> None:
    paths = [
        "/platform/capability-packs/unknown.pack/adoption-template",
        "/platform/capability-packs/unknown.pack/observability-summary",
        "/platform/capability-packs/unknown.pack/activation-readiness",
        "/platform/capability-packs/unknown.pack/runbook-readiness",
        "/platform/capability-packs/unknown.pack/governance-status",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 404
        assert "Unknown capability pack" in response.json()["detail"]
