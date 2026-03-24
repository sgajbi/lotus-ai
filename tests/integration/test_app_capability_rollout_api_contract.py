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
