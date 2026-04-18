from fastapi.testclient import TestClient


def test_workflow_pack_registry_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert body["registration_count"] == 2
    assert body["registered_count"] == 1
    assert body["production_eligible_count"] == 0
    assert body["registrations"][0]["pack_id"] == "advisor_brief.pack"
    assert body["registrations"][0]["version"] == "v1"
    assert body["registrations"][0]["registration_status"] == "REGISTERED"
    assert body["registrations"][0]["activation_state"] == "PILOT"


def test_workflow_pack_registration_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry/advisor_brief.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["pack_id"] == "advisor_brief.pack"
    assert body["registration"]["version"] == "v1"
    assert body["registration"]["owner_repository"] == "lotus-gateway"
    assert body["registration"]["workflow_authority_owner"] == "lotus-gateway"
    assert body["registration"]["definition_ref"] == (
        "repo://lotus-gateway/src/app/contracts/advisor_brief.py"
    )
    assert any(
        definition_ref["repository"] == "lotus-gateway"
        and definition_ref["path"] == "src/app/services/advisor_brief_service.py"
        and definition_ref["required_for_registration"] is True
        for definition_ref in body["registration"]["definition_refs"]
    )
    assert body["denied_without_registration"] is True
    assert any(
        rule["rule_id"] == "registered_entries_require_scope" for rule in body["validation_rules"]
    )


def test_workflow_pack_registration_detail_route_rejects_unknown_registration(
    client: TestClient,
) -> None:
    response = client.get("/platform/workflow-packs/registry/unknown.pack/v1")

    assert response.status_code == 404
    assert "Unknown workflow-pack registration" in response.json()["detail"]
