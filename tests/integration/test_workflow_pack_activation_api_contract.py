from fastapi.testclient import TestClient


def test_workflow_pack_eligibility_route_allows_registered_scope(client: TestClient) -> None:
    response = client.post(
        "/platform/workflow-packs/eligibility/evaluate",
        json={
            "pack_id": "advisor_brief.pack",
            "version": "v1",
            "caller_app": "lotus-gateway",
            "environment": "QA",
            "caller_identity_class": "INTERNAL_SERVICE",
            "workflow_surface": "advisor-brief-panel",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["allowed"] is True
    assert body["eligibility_result"] == "ALLOWED"
    assert body["evaluated_registration_ref"] == "advisor_brief.pack@v1"


def test_workflow_pack_eligibility_route_denies_out_of_scope_caller(client: TestClient) -> None:
    response = client.post(
        "/platform/workflow-packs/eligibility/evaluate",
        json={
            "pack_id": "advisor_brief.pack",
            "version": "v1",
            "caller_app": "lotus-manage",
            "environment": "QA",
            "caller_identity_class": "INTERNAL_SERVICE",
            "workflow_surface": "advisor-brief-panel",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["allowed"] is False
    assert body["eligibility_result"] == "DENIED_CALLER_SCOPE"
    assert any("caller application" in reason for reason in body["denial_reasons"])


def test_workflow_pack_eligibility_route_denies_unknown_registration(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/eligibility/evaluate",
        json={
            "pack_id": "unknown.pack",
            "version": "v1",
            "caller_app": "lotus-gateway",
            "environment": "QA",
            "caller_identity_class": "INTERNAL_SERVICE",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["allowed"] is False
    assert body["eligibility_result"] == "DENIED_NOT_REGISTERED"
