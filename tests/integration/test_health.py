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


def test_async_runtime_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["queue_mode"] == "DISABLED"
    assert body["worker_mode"] == "DOCUMENTED_ONLY"
    assert body["queue_backend"] == "none"
    assert body["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["supported_queue_backends"][1]["backend_id"] == "redis_queue"
    assert body["active_worker_execution"] == "none"
    assert body["supported_worker_executions"][0]["worker_id"] == "none"
    assert body["supported_worker_executions"][2]["worker_id"] == "queue_backed_workers"
    assert body["active_worker_count"] == 0
    assert body["enqueued_job_count"] == 1
    assert body["recorded_job_count"] == 2
    assert any(job["job_type"] == "retrieval_indexing" for job in body["supported_job_types"])


def test_async_queue_backend_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/queue-backends")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["active_queue_backend"] == "none"
    assert body["backend_count"] == 3
    assert body["backends"][0]["backend_id"] == "none"
    assert body["backends"][1]["backend_id"] == "redis_queue"
    assert body["backends"][2]["backend_id"] == "kafka_orchestrated"


def test_async_worker_execution_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/worker-executions")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["active_worker_execution"] == "none"
    assert body["worker_count"] == 3
    assert body["workers"][0]["worker_id"] == "none"
    assert body["workers"][1]["worker_id"] == "in_process_stub"
    assert body["workers"][2]["worker_id"] == "queue_backed_workers"


def test_async_activation_readiness_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["activation_ready"] is False
    assert body["queue_backend"] == "none"
    assert body["worker_execution"] == "none"
    assert body["supported_job_type_count"] == 3
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 4


def test_async_runbook_readiness_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "async_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


def test_async_governance_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 2
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert len(body["governance_summary"]) == 2


def test_async_job_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["job_count"] == 2
    assert body["queued_job_count"] == 1
    assert body["jobs"][0]["job_id"] == "asyncjob_retrieval_indexing_001"
    assert body["jobs"][1]["status"] == "SUPERSEDED"
    assert body["jobs"][1]["related_evaluation_run_id"] == "foundation_eval_2026_03_21_001"


def test_async_job_detail_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/jobs/asyncjob_retrieval_indexing_001")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["job"]["job_type"] == "retrieval_indexing"
    assert body["job"]["status"] == "QUEUED"
    assert body["job"]["related_evaluation_run_id"] is None


def test_async_job_detail_route_returns_not_found_for_unknown_job() -> None:
    client = TestClient(app)

    response = client.get("/platform/async/jobs/missing_async_job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Async job artifact 'missing_async_job' was not found."


def test_async_job_submit_route_returns_rejected_contract_response() -> None:
    client = TestClient(app)

    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-001",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["submission_status"] == "REJECTED"
    assert body["accepted"] is False
    assert body["job_id"] is None
    assert body["queue_mode"] == "DISABLED"


def test_async_job_submit_route_returns_not_found_for_unknown_job_type() -> None:
    client = TestClient(app)

    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "missing_job_type",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-002",
            "payload_summary": "Unknown async work.",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown lotus-ai async job type: missing_job_type"


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
        fixture["fixture_id"] == "task_capability_contracts"
        and fixture["manifest_path"] == "docs/evals/fixtures/tasks.contracts/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
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
    assert any(
        fixture["fixture_id"] == "provider_policy_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/providers.policy/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "safety_policy_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/safety.policy/basic_cases.json"
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
    assert body["staged_case_count"] == 12
    assert [item["seam_id"] for item in body["seam_coverage"]] == [
        "task_execution",
        "retrieval",
        "provider_policy",
        "safety_policy",
    ]
    assert body["seam_coverage"][0]["staged_fixture_count"] == 3
    assert body["seam_coverage"][0]["staged_case_count"] == 6
    assert body["recorded_run_count"] == 2
    assert body["latest_recorded_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["latest_recorded_run_status"] == "RECORDED"
    assert body["evaluation_runner_active"] is False


def test_evaluation_run_catalog_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run_count"] == 2
    assert body["latest_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["status_counts"]["RECORDED"] == 1
    assert body["status_counts"]["SUPERSEDED"] == 1
    assert body["runs"][0]["staged_case_count"] == 12
    assert body["runs"][1]["status"] == "SUPERSEDED"


def test_evaluation_run_detail_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/runs/foundation_eval_2026_03_22_001")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run"]["run_id"] == "foundation_eval_2026_03_22_001"
    assert body["run"]["seam_coverage"][0]["seam_id"] == "task_execution"


def test_evaluation_run_detail_route_returns_superseded_artifact() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/runs/foundation_eval_2026_03_21_001")

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_id"] == "foundation_eval_2026_03_21_001"
    assert body["run"]["status"] == "SUPERSEDED"
    assert body["run"]["seam_coverage"][-1]["seam_id"] == "safety_policy"
    assert body["run"]["seam_coverage"][-1]["staged_fixture_count"] == 0


def test_evaluation_run_detail_route_returns_not_found_for_unknown_run() -> None:
    client = TestClient(app)

    response = client.get("/platform/evals/runs/missing_run")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evaluation run artifact 'missing_run' was not found."


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


def test_provider_activation_readiness_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/providers/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["provider_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 4


def test_provider_runbook_readiness_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/providers/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "provider_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


def test_provider_governance_status_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/providers/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 2
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert len(body["governance_summary"]) == 2


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
    assert body["async_runtime"]["queue_mode"] == "DISABLED"
    assert body["async_runtime"]["worker_mode"] == "DOCUMENTED_ONLY"
    assert body["async_runtime"]["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["async_runtime"]["active_worker_execution"] == "none"
    assert (
        body["async_runtime"]["supported_worker_executions"][2]["worker_id"]
        == "queue_backed_workers"
    )
    assert body["async_runtime"]["active_worker_count"] == 0
    assert body["async_runtime"]["enqueued_job_count"] == 1
    assert body["async_runtime"]["recorded_job_count"] == 2
    assert body["async_governance"]["governance_ready"] is False
    assert body["async_governance"]["blocking_area_count"] == 2
    assert body["async_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["async_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["provider_governance"]["governance_ready"] is False
    assert body["provider_governance"]["blocking_area_count"] == 2
    assert body["provider_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["provider_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["evaluation_runtime"]["manifest_version"] == "foundation.v1"
    assert body["evaluation_runtime"]["evidence_category_count"] == 5
    assert body["evaluation_runtime"]["staged_case_count"] == 12
    assert body["evaluation_runtime"]["seam_coverage"][0]["seam_id"] == "task_execution"
    assert body["evaluation_runtime"]["seam_coverage"][0]["staged_fixture_count"] == 3
    assert body["evaluation_runtime"]["recorded_run_count"] == 2
    assert body["evaluation_runtime"]["latest_recorded_run_id"] == "foundation_eval_2026_03_22_001"
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


def test_retrieval_activation_readiness_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["retrieval_mode"] == "disabled"
    assert body["embedding_provider_mode"] == "disabled"
    assert body["activation_ready"] is False
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 4


def test_retrieval_runbook_readiness_route() -> None:
    client = TestClient(app)

    response = client.get("/platform/retrieval/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "retrieval_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


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
