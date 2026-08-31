from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.retrieval_ingestion_async_execution import run_next_retrieval_ingestion_job
from app.services.retrieval_async_execution import run_next_retrieval_index_job
from fastapi.testclient import TestClient


def test_retrieval_source_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["vector_store"] == "postgresql+pgvector"
    assert any(source["source_id"] == "lotus-platform-rfcs" for source in body["sources"])


def test_retrieval_source_governance_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/source-governance")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["searchable_source_count"] == 0
    assert body["index_pending_source_count"] >= 2
    assert body["blocked_source_count"] >= 1
    assert any(
        source["source_id"] == "lotus-platform-rfcs"
        and source["governance_status"] == "INDEX_PENDING"
        for source in body["sources"]
    )
    assert any(
        source["source_id"] == "lotus-platform-standards"
        and source["governance_status"] == "BLOCKED_BY_SOURCE"
        for source in body["sources"]
    )


def test_retrieval_document_governance_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/document-governance")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["searchable_document_count"] == 0
    assert body["refresh_pending_document_count"] == 0
    assert body["withdrawn_document_count"] >= 1
    assert body["blocked_document_count"] == 0
    assert any(
        document["document_id"] == "lotus-platform-rfc-0069"
        and document["governance_status"] == "INDEX_PENDING"
        for document in body["documents"]
    )


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
    assert body["document_version_count"] >= 5
    assert body["ingestion_job_count"] >= 3


def test_retrieval_ingestion_status_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/ingestion-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["ingestion_delivery_stage"] == "OPERATIONALLY_HARDENED"
    assert body["live_ingestion_enabled"] is True
    assert body["document_version_count"] >= 5
    assert body["withdrawn_document_version_count"] >= 1
    assert body["blocked_ingestion_job_count"] >= 1
    assert body["artifact_backed_job_count"] == 0
    assert body["recent_document_versions"]
    assert body["recent_ingestion_jobs"]


def test_retrieval_ingestion_jobs_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/ingestion-jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert any(job["job_id"] == "ingjob_lotus_platform_rfcs_refresh_0069" for job in body["jobs"])


def test_retrieval_ingestion_job_detail_route(client: TestClient) -> None:
    response = client.get(
        "/platform/retrieval/ingestion-jobs/ingjob_lotus_platform_rfcs_refresh_0069"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["source_id"] == "lotus-platform-rfcs"
    assert body["job"]["artifact_refs"] == []
    assert any(step["step_id"].endswith(".index_followthrough") for step in body["steps"])


def test_retrieval_ingestion_job_submit_async_route(client: TestClient) -> None:
    response = client.post(
        "/platform/retrieval/ingestion-jobs/ingjob_lotus_platform_rfcs_refresh_0069/submit-async",
        params={
            "caller_app": "lotus-platform",
            "correlation_id": "corr-ret-ingest-submit-001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["target_id"] == "ingjob_lotus_platform_rfcs_refresh_0069"


def test_retrieval_ingestion_job_detail_reflects_runtime_backed_completion(
    client: TestClient,
) -> None:
    submit_response = client.post(
        "/platform/retrieval/ingestion-jobs/ingjob_lotus_platform_rfcs_refresh_0069/submit-async",
        params={
            "caller_app": "lotus-platform",
            "correlation_id": "corr-ret-ingest-submit-002",
        },
    )
    async_job_id = submit_response.json()["job_id"]
    run_next_retrieval_ingestion_job(worker_id="worker-a")

    response = client.get(
        "/platform/retrieval/ingestion-jobs/ingjob_lotus_platform_rfcs_refresh_0069"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "COMPLETED"
    assert len(body["job"]["artifact_refs"]) == 1
    assert body["steps"][2]["runtime_status"] == "COMPLETED"
    assert body["steps"][2]["linked_async_job_id"] == async_job_id
    assert body["steps"][3]["linked_async_job_id"] is not None


def test_retrieval_execution_status_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/execution-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_mode"] == "disabled"
    assert body["execution_stage"] == "SEARCH_DISABLED"
    assert body["live_search_enabled"] is False
    assert body["live_indexing_enabled"] is True
    assert body["embedding_execution_enabled"] is False
    assert body["route_mode"] == "UNIFIED_INTERNAL"
    assert body["split_route_degraded"] is False


def test_retrieval_execution_status_route_reports_live_search_when_enabled(
    client: TestClient,
) -> None:
    from app.config import settings
    from app.services.retrieval_store import get_retrieval_repository

    settings.retrieval_mode = "enabled"
    get_retrieval_repository().set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    response = client.get("/platform/retrieval/execution-status")

    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_mode"] == "enabled"
    assert body["execution_stage"] == "LIVE_SEARCH"
    assert body["live_search_enabled"] is True
    assert "searchable promoted document" in body["message"]


def test_retrieval_split_active_runtime_routes_are_reported_explicitly(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.deployment_split_stage = "retrieval_split_active"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(
            governance_ready=False,
            governance_summary=["Retrieval runbook readiness remains blocked."],
        ),
    )

    split_response = client.get("/platform/deployment-split/runtime-status")
    retrieval_response = client.get("/platform/retrieval/execution-status")

    assert split_response.status_code == 200
    assert retrieval_response.status_code == 200

    split_body = split_response.json()
    retrieval_body = retrieval_response.json()
    assert split_body["effective_stage"] == "RETRIEVAL_SPLIT_ACTIVE"
    assert split_body["degraded"] is True
    assert any(
        route["route_id"] == "retrieval_search_execution"
        and route["route_mode"] == "PLANE_SPLIT_ACTIVE"
        and route["owning_plane"] == "retrieval"
        for route in split_body["routes"]
    )
    assert retrieval_body["owning_plane"] == "retrieval"
    assert retrieval_body["route_mode"] == "PLANE_SPLIT_ACTIVE"
    assert retrieval_body["split_route_degraded"] is True


def test_retrieval_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["embedding_execution_enabled"] is False
    assert body["ingestion_execution_enabled"] is True
    assert body["activation_ready"] is False
    assert any("Retrieval mode is not enabled" in finding for finding in body["blocking_findings"])
    assert len(body["activation_path"]) == 4


def test_retrieval_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 6
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "retrieval_operational_runbook"
    assert body["items"][0]["status"] == "DOCUMENTED_ONLY"
    assert body["items"][2]["status"] == "DOCUMENTED_ONLY"
    assert body["items"][3]["runbook_id"] == "retrieval_embedding_dependency_review"


def test_retrieval_evidence_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["evidence_ready"] is False
    assert body["required_item_count"] == 6
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["evidence_id"] == "retrieval_fixture_coverage_pack"
    assert body["items"][1]["status"] == "NOT_READY"
    assert body["items"][3]["evidence_id"] == "retrieval_embedding_runtime_pack"
    assert body["approval_gate"]["domain_id"] == "retrieval_execution"
    assert body["approval_gate"]["evidence_state"] == "STAGED_ONLY"
    assert (
        body["approval_gate"]["latest_historical_baseline_run_id"]
        == "foundation_eval_2026_03_22_001"
    )


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
    assert body["evidence_readiness"]["approval_gate"]["domain_id"] == "retrieval_execution"
    assert body["corpus_change_review_ready"] is False
    assert len(body["governance_summary"]) == 4


def test_retrieval_evidence_readiness_route_prefers_runtime_backed_pass_evidence(
    client: TestClient,
) -> None:
    for fixture_id in ("retrieval_citation_examples", "retrieval_embedding_examples"):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id=fixture_id,
                caller_app="lotus-platform",
                correlation_id=f"corr-{fixture_id}",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")

    response = client.get("/platform/retrieval/evidence-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["approval_gate"]["evidence_state"] == "RUNTIME_PASS"
    assert body["approval_gate"]["approval_ready"] is True


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
    assert body["embedding_execution_enabled"] is False


def test_retrieval_index_job_detail_route(client: TestClient) -> None:
    response = client.get("/platform/retrieval/index-jobs/retjob_lotus_platform_rfcs")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["source_id"] == "lotus-platform-rfcs"
    assert any(step["step_id"].endswith(".embedding_generation") for step in body["steps"])


def test_retrieval_index_job_submit_async_route(client: TestClient) -> None:
    response = client.post(
        "/platform/retrieval/index-jobs/retjob_lotus_platform_rfcs/submit-async",
        params={
            "caller_app": "lotus-platform",
            "correlation_id": "corr-ret-submit-001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["target_id"] == "retjob_lotus_platform_rfcs"


def test_retrieval_index_job_detail_reflects_runtime_backed_completion(client: TestClient) -> None:
    submit_response = client.post(
        "/platform/retrieval/index-jobs/retjob_lotus_platform_rfcs/submit-async",
        params={
            "caller_app": "lotus-platform",
            "correlation_id": "corr-ret-submit-002",
        },
    )
    async_job_id = submit_response.json()["job_id"]
    run_next_retrieval_index_job(worker_id="worker-a")

    response = client.get("/platform/retrieval/index-jobs/retjob_lotus_platform_rfcs")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "COMPLETED"
    assert body["steps"][2]["runtime_status"] == "COMPLETED"
    assert body["steps"][2]["linked_async_job_id"] == async_job_id


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
    assert body["execution_stage"] == "CATALOG_ONLY"
    assert body["hits"][0]["source_id"] == "lotus-platform-rfcs"
    assert body["hits"][0]["document_id"] == "lotus-platform-rfc-0069"
    assert body["hits"][0]["document_location"]
    assert body["hits"][0]["active_version_id"] == "ver_lotus_platform_rfc_0069_2026_03_22"
    assert body["hits"][0]["citation_ref"]
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

    assert response.status_code == 403
    assert "approved policy scope" in response.json()["detail"]


def test_retrieval_search_route_blocks_unknown_caller(client: TestClient) -> None:
    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "shared ai platform service",
            "caller_app": "unknown-app",
            "correlation_id": "corr-ret-unknown",
        },
    )

    assert response.status_code == 403
    assert "not registered" in response.json()["detail"]


def test_retrieval_search_route_defaults_to_caller_allowed_sources(client: TestClient) -> None:
    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "shared ai platform service",
            "caller_app": "lotus-workbench",
            "correlation_id": "corr-ret-default-sources",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["hits"][0]["source_id"] in {"lotus-platform-rfcs", "lotus-ai-architecture"}


def test_retrieval_search_route_returns_live_hits_when_enabled(client: TestClient) -> None:
    from app.config import settings
    from app.services.retrieval_store import get_retrieval_repository

    settings.retrieval_mode = "enabled"
    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "shared ai platform service",
            "caller_app": "lotus-workbench",
            "correlation_id": "corr-ret-live-1",
            "source_ids": ["lotus-platform-rfcs"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["execution_stage"] == "LIVE_SEARCH"
    assert body["hits"][0]["source_id"] == "lotus-platform-rfcs"
    assert body["hits"][0]["document_id"] == "lotus-platform-rfc-0069"
    assert body["hits"][0]["chunk_id"] == "chunk_rfc_0069_0001"
    assert body["hits"][0]["document_location"]
    assert body["hits"][0]["active_version_id"] == "ver_lotus_platform_rfc_0069_2026_03_22"
    assert body["hits"][0]["citation_ref"]


def test_retrieval_search_route_rejects_live_requests_after_rollback(client: TestClient) -> None:
    from app.config import settings
    from app.services.retrieval_store import get_retrieval_repository

    settings.retrieval_mode = "enabled"
    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="STAGED",
    )

    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "shared ai platform service",
            "caller_app": "lotus-workbench",
            "correlation_id": "corr-ret-live-rollback-1",
            "source_ids": ["lotus-platform-rfcs"],
        },
    )

    assert response.status_code == 409
    assert "indexing is still pending" in response.json()["detail"]


def test_retrieval_governance_routes_reflect_indexed_searchable_documents(
    client: TestClient,
) -> None:
    from app.services.retrieval_store import get_retrieval_repository

    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    source_response = client.get("/platform/retrieval/source-governance")
    document_response = client.get("/platform/retrieval/document-governance")

    assert source_response.status_code == 200
    assert document_response.status_code == 200

    source_body = source_response.json()
    document_body = document_response.json()
    assert source_body["searchable_source_count"] >= 1
    assert any(
        source["source_id"] == "lotus-platform-rfcs"
        and source["governance_status"] == "SEARCH_ENABLED"
        and source["search_enabled"] is True
        for source in source_body["sources"]
    )
    assert document_body["searchable_document_count"] >= 2
    assert any(
        document["document_id"] == "lotus-platform-rfc-0069"
        and document["governance_status"] == "SEARCH_ENABLED"
        and document["search_enabled"] is True
        for document in document_body["documents"]
    )
