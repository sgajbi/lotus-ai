from fastapi.testclient import TestClient


def test_retrieval_source_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["vector_store"] == "postgresql+pgvector"
    assert any(source["source_id"] == "lotus-platform-rfcs" for source in body["sources"])


def test_retrieval_index_status_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/index-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert any(source["source_id"] == "lotus-platform-rfcs" for source in body["sources"])


def test_retrieval_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_store_mode"] == "memory"
    assert body["retrieval_store_status"] == "READY"
    assert body["source_count"] >= 4


def test_retrieval_execution_status_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/execution-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_mode"] == "disabled"
    assert body["execution_stage"] == "SEARCH_DISABLED"
    assert body["live_search_enabled"] is False


def test_retrieval_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 4


def test_retrieval_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "retrieval_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


def test_retrieval_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["evidence_id"] == "retrieval_fixture_coverage_pack"
    assert body["items"][1]["status"] == "NOT_READY"


def test_retrieval_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 3
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert body["evidence_readiness"]["evidence_ready"] is False
    assert len(body["governance_summary"]) == 3


def test_retrieval_index_jobs_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/index-jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert any(job["source_id"] == "lotus-platform-rfcs" for job in body["jobs"])


def test_retrieval_indexing_policy_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/indexing-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["persistence_strategy"] == "postgresql+pgvector"
    assert body["retrieval_store_mode"] == "memory"


def test_retrieval_index_job_detail_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/index-jobs/retjob_lotus_platform_rfcs")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["source_id"] == "lotus-platform-rfcs"
    assert any(step["step_id"].endswith(".embedding_generation") for step in body["steps"])


def test_retrieval_documents_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/sources/lotus-platform-rfcs/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == "lotus-platform-rfcs"
    assert any(
        document["document_id"] == "lotus-platform-rfc-0069" for document in body["documents"]
    )


def test_retrieval_chunks_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/documents/lotus-platform-rfc-0069/chunks")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == "lotus-platform-rfc-0069"
    assert any(chunk["chunk_id"] == "chunk_rfc_0069_0001" for chunk in body["chunks"])


def test_retrieval_search_route_returns_catalog_only_hits_for_enabled_sources(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "shared ai platform service",
            "caller_app": "lotus-workbench",
            "correlation_id": "corr-ret-2",
            "source_ids": ["lotus-platform-rfcs"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["hits"][0]["source_id"] == "lotus-platform-rfcs"
    assert "catalog-only hits" in body["message"]


def test_retrieval_search_route_rejects_disabled_source_filter(client: TestClient) -> None:
    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "platform observability standards",
            "caller_app": "lotus-workbench",
            "correlation_id": "corr-ret-3",
            "source_ids": ["lotus-platform-standards"],
        },
    )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"]
