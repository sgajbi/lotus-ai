from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_correlation_header_propagation() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_platform_capabilities_contract() -> None:
    client = TestClient(app)
    response = client.get("/platform/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert any(task["task_id"] == "explain.v1" for task in body["tasks"])


def test_evaluation_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/catalog")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert any(
        category["category_id"] == "task_contract" for category in body["evidence_categories"]
    )
    assert any(
        fixture["fixture_id"] == "explanation_task_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/explain.v1/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "summarization_task_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/summarize.v1/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "retrieval_citation_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/retrieval.search/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )


def test_evaluation_runtime_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert body["evidence_category_count"] == 5
    assert body["staged_case_count"] == 6
    assert body["evaluation_runner_active"] is False


def test_evaluation_fixture_detail_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/fixtures/retrieval_citation_examples")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert body["fixture"]["fixture_id"] == "retrieval_citation_examples"
    assert body["task_id"] == "retrieval.search.v1"
    assert len(body["cases"]) == 2
    assert body["cases"][0]["case_id"] == "search_rfc_answer_requires_citation"


def test_evaluation_fixture_detail_route_returns_not_found_for_unknown_fixture() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/fixtures/missing_fixture")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evaluation fixture family 'missing_fixture' was not found."


def test_provider_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["runtime_execution_enabled"] is False
    assert any(provider["provider_id"] == "text.stub" for provider in body["providers"])


def test_provider_policy_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/providers/policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert any(policy["capability"] == "TEXT_GENERATION" for policy in body["policies"])


def test_safety_policy_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/safety/policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["safety_mode"] == "documented_only"
    assert any(control["control_id"] == "response_labeling" for control in body["controls"])
    assert any(task["task_id"] == "explain.v1" for task in body["task_policies"])


def test_safety_runtime_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/safety/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["safety_mode"] == "documented_only"
    assert body["runtime_redaction_active"] is False
    assert body["enforced_control_ids"] == ["response_labeling", "correlation_and_audit"]


def test_platform_runtime_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["delivery_phase"] == "foundation"
    assert body["startup_readiness_policy"] == "warn"
    assert body["readiness_probe_policy"] == "observe"
    assert body["audit_store"]["mode"] == "memory"
    assert body["audit_store"]["status"] == "READY"
    assert body["retrieval_store"]["mode"] == "memory"
    assert body["retrieval_store"]["status"] == "READY"
    assert body["evaluation_runtime"]["manifest_version"] == "foundation.v1"
    assert body["evaluation_runtime"]["evidence_category_count"] == 5
    assert body["evaluation_runtime"]["staged_case_count"] == 6
    assert body["evaluation_runtime"]["evaluation_runner_active"] is False
    assert body["prompt_runtime"]["selection_mode"] == "STATIC_ACTIVE"
    assert body["prompt_runtime"]["active_prompt_count"] >= 7
    assert any(
        selection["task_id"] == "explain.v1" for selection in body["prompt_runtime"]["selections"]
    )
    assert body["safety_runtime"]["runtime_redaction_active"] is False
    assert body["safety_runtime"]["enforced_control_ids"] == [
        "response_labeling",
        "correlation_and_audit",
    ]
    assert body["migration_contract_enforced"] is True
    assert body["startup_readiness_blocking"] is False
    assert body["prompt_count"] >= 3


def test_task_execute_contract() -> None:
    client = TestClient(app)
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-456",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED", "violations": 2},
                "source_refs": ["lotus-manage:run:reb_002"],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "explain.v1"
    assert body["status"] == "COMPLETED"
    assert body["audit"]["stubbed"] is True
    assert body["audit"]["prompt_version"] == "foundation.explain.v1"
    assert body["audit"]["safety"]["safety_mode"] == "documented_only"
    assert body["audit"]["safety"]["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert len(body["evidence"]["descriptors"]) == 5
    assert body["evidence"]["descriptors"][0]["evidence_type"] == "task_contract"
    assert body["result"]["structured_output"]["caller_app"] == "lotus-manage"


def test_prompt_registry_routes() -> None:
    client = TestClient(app)

    list_response = client.get("/platform/prompts")
    assert list_response.status_code == 200
    assert any(prompt["task_id"] == "explain.v1" for prompt in list_response.json())
    assert all(prompt["lifecycle_status"] == "ACTIVE" for prompt in list_response.json())

    detail_response = client.get("/platform/prompts/explain.v1")
    assert detail_response.status_code == 200
    assert detail_response.json()["prompt_version"] == "foundation.explain.v1"
    assert detail_response.json()["management_mode"] == "SEEDED_MEMORY"


def test_prompt_governance_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/prompts/governance")

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_store_mode"] == "memory"
    assert body["management_mode"] == "SEEDED_MEMORY"
    assert body["runtime_mutation_enabled"] is False
    assert body["promotion_write_api_enabled"] is False
    assert body["active_prompt_count"] >= 7


def test_prompt_runtime_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/prompts/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["prompt_store_mode"] == "memory"
    assert body["selection_mode"] == "STATIC_ACTIVE"
    assert any(selection["task_id"] == "explain.v1" for selection in body["selections"])


def test_service_metadata_exposes_store_modes() -> None:
    client = TestClient(app)

    response = client.get("/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["auditStoreMode"] == "memory"
    assert body["promptStoreMode"] == "memory"
    assert body["retrievalStoreMode"] == "memory"
    assert body["startupReadinessPolicy"] == "warn"
    assert body["readinessProbePolicy"] == "observe"


def test_audit_record_route_returns_saved_execution() -> None:
    client = TestClient(app)
    execute_response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "summarize.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": "corr-789",
            },
            "context": {
                "summary": "Summarize proposal workflow",
                "payload": {"status": "PENDING_REVIEW", "approvals": 1},
                "source_refs": ["lotus-advise:proposal:prop_001"],
            },
        },
    )
    request_id = execute_response.json()["audit"]["request_id"]

    audit_response = client.get(f"/ai/audit/{request_id}")
    assert audit_response.status_code == 200
    assert audit_response.json()["caller_app"] == "lotus-advise"
    assert audit_response.json()["prompt_version"] == "foundation.summarize.v1"
    assert audit_response.json()["safety_mode"] == "documented_only"
    assert audit_response.json()["enforced_safety_controls"] == [
        "response_labeling",
        "correlation_and_audit",
    ]


def test_retrieval_source_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["vector_store"] == "postgresql+pgvector"
    assert any(source["source_id"] == "lotus-platform-rfcs" for source in body["sources"])


def test_retrieval_index_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/index-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert any(source["source_id"] == "lotus-platform-rfcs" for source in body["sources"])


def test_retrieval_runtime_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_store_mode"] == "memory"
    assert body["retrieval_store_status"] == "READY"
    assert body["source_count"] >= 4


def test_retrieval_execution_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/execution-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_mode"] == "disabled"
    assert body["execution_stage"] == "SEARCH_DISABLED"
    assert body["live_search_enabled"] is False


def test_retrieval_index_jobs_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/index-jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert any(job["source_id"] == "lotus-platform-rfcs" for job in body["jobs"])


def test_retrieval_indexing_policy_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/indexing-policy")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["persistence_strategy"] == "postgresql+pgvector"
    assert body["retrieval_store_mode"] == "memory"


def test_retrieval_index_job_detail_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/index-jobs/retjob_lotus_platform_rfcs")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["source_id"] == "lotus-platform-rfcs"
    assert any(step["step_id"].endswith(".embedding_generation") for step in body["steps"])


def test_retrieval_documents_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/sources/lotus-platform-rfcs/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == "lotus-platform-rfcs"
    assert any(
        document["document_id"] == "lotus-platform-rfc-0069" for document in body["documents"]
    )


def test_retrieval_chunks_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/documents/lotus-platform-rfc-0069/chunks")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == "lotus-platform-rfc-0069"
    assert any(chunk["chunk_id"] == "chunk_rfc_0069_0001" for chunk in body["chunks"])


def test_retrieval_search_route_returns_conflict_when_disabled() -> None:
    client = TestClient(app)

    response = client.post(
        "/platform/retrieval/search",
        json={
            "query": "What does RFC-0069 say?",
            "caller_app": "lotus-workbench",
            "correlation_id": "corr-ret-2",
        },
    )

    assert response.status_code == 409
    assert "Retrieval search is not enabled yet" in response.json()["detail"]
