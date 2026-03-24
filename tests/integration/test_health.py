from fastapi.testclient import TestClient


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_correlation_header_propagation(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_platform_capabilities_contract(client: TestClient) -> None:
    response = client.get("/platform/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert any(task["task_id"] == "explain.v1" for task in body["tasks"])


def test_task_execution_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-summary-route-1",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED"},
                "source_refs": [],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-summary-route-2",
            },
            "context": {
                "summary": "Search Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    response = client.get("/platform/tasks/execution-summary", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["sampled_record_limit"] == 20
    assert body["sampled_record_count"] >= 2
    assert body["stubbed_execution_count"] >= 1
    assert body["non_stubbed_execution_count"] >= 1
    assert any(sample["provider_mode"] == "catalog_only" for sample in body["provider_modes"])
    assert any(sample["provider_mode"] != "catalog_only" for sample in body["provider_modes"])


def test_task_execution_evidence_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-evidence-route-1",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-evidence-route-2",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    response = client.get("/platform/tasks/evidence-summary", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["sampled_record_limit"] == 20
    assert body["sampled_record_count"] >= 2
    assert body["citation_bearing_execution_count"] >= 2
    assert body["citation_backed_answer_count"] >= 1
    assert body["refused_answer_count"] >= 1
    assert any(sample["answer_mode"] == "CITATION_BACKED" for sample in body["answer_modes"])
    assert any(
        sample["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT" for sample in body["answer_modes"]
    )


def test_task_retrieval_execution_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-rsummary-route-1",
            },
            "context": {
                "summary": "Search Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-rsummary-route-2",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    response = client.get("/platform/tasks/retrieval-summary", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["sampled_record_limit"] == 20
    assert body["sampled_record_count"] >= 2
    assert body["retrieval_execution_count"] >= 2
    assert body["knowledge_search_execution_count"] >= 1
    assert body["knowledge_answer_execution_count"] >= 1
    assert body["refused_answer_count"] >= 1
    assert any(sample["retrieval_status"] == "READY" for sample in body["retrieval_statuses"])
    assert any(sample["source_id"] == "lotus-platform-rfcs" for sample in body["sources"])
    assert any(
        sample["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT" for sample in body["answer_modes"]
    )


def test_platform_runtime_status_route(client: TestClient) -> None:
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
    assert body["async_runtime"]["queue_mode"] == "STUBBED"
    assert body["async_runtime"]["worker_mode"] == "STUBBED"
    assert body["async_runtime"]["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["async_runtime"]["supported_queue_backends"][1]["backend_id"] == "service_database"
    assert body["async_runtime"]["queue_backend"] == "service_database"
    assert body["async_runtime"]["active_worker_execution"] == "in_process_stub"
    assert (
        body["async_runtime"]["supported_worker_executions"][2]["worker_id"]
        == "queue_backed_workers"
    )
    assert body["async_runtime"]["active_worker_count"] == 0
    assert body["async_runtime"]["enqueued_job_count"] == 0
    assert body["async_runtime"]["recorded_job_count"] == 2
    assert (
        "retrieval indexing and evaluation execution already running through the runtime-backed in-process worker path"
        in body["async_runtime"]["message"]
    )
    assert body["async_governance"]["governance_ready"] is False
    assert body["async_governance"]["blocking_area_count"] == 2
    assert body["async_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["async_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["provider_governance"]["governance_ready"] is False
    assert body["provider_governance"]["blocking_area_count"] == 3
    assert body["provider_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["provider_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["provider_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["provider_operations"]["operations_state"] == "ROLLOUT_BLOCKED"
    assert body["provider_operations"]["runtime_execution_enabled"] is False
    assert body["provider_operations"]["quota_policy"]["quota_enforced"] is False
    assert body["provider_operations"]["budget_policy"]["budget_enforced"] is False
    assert body["retrieval_governance"]["governance_ready"] is False
    assert body["retrieval_governance"]["blocking_area_count"] == 3
    assert body["retrieval_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["retrieval_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["retrieval_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["prompt_governance"]["governance_ready"] is False
    assert body["prompt_governance"]["blocking_area_count"] == 2
    assert body["prompt_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["prompt_governance"]["runbook_readiness"]["runbook_ready"] is True
    assert body["prompt_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["evaluation_runtime"]["manifest_version"] == "foundation.v1"
    assert body["evaluation_runtime"]["evidence_category_count"] == 6
    assert body["evaluation_runtime"]["staged_case_count"] == 32
    assert body["evaluation_runtime"]["seam_coverage"][0]["seam_id"] == "async_execution"
    assert body["evaluation_runtime"]["seam_coverage"][0]["staged_fixture_count"] == 1
    assert body["evaluation_runtime"]["seam_coverage"][1]["staged_fixture_count"] == 3
    assert body["evaluation_runtime"]["seam_coverage"][2]["staged_fixture_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][2]["staged_case_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][4]["staged_fixture_count"] == 5
    assert body["evaluation_runtime"]["seam_coverage"][4]["staged_case_count"] == 12
    assert body["evaluation_runtime"]["seam_coverage"][5]["staged_fixture_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][5]["staged_case_count"] == 6
    assert body["evaluation_runtime"]["approval_gates"][0]["domain_id"] == "prompt_rollout"
    assert body["evaluation_runtime"]["approval_gates"][1]["domain_id"] == "retrieval_execution"
    assert body["evaluation_runtime"]["approval_gates"][2]["domain_id"] == "provider_execution"
    assert body["evaluation_runtime"]["approval_gates"][3]["domain_id"] == "safety_enforcement"
    assert body["evaluation_runtime"]["recorded_run_count"] == 2
    assert body["evaluation_runtime"]["latest_recorded_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["evaluation_runtime"]["evaluation_runner_active"] is True
    assert body["prompt_runtime"]["selection_mode"] == "ROLLOUT_STATE_ACTIVE"
    assert body["prompt_runtime"]["rollout_mode"] == "GOVERNED_CONTROL_ACTIONS"
    assert body["prompt_runtime"]["active_prompt_count"] >= 7
    assert body["prompt_runtime"]["candidate_prompt_count"] == 0
    assert any(
        selection["task_id"] == "explain.v1" for selection in body["prompt_runtime"]["selections"]
    )
    assert any(state["task_id"] == "explain.v1" for state in body["prompt_runtime"]["rollout_states"])
    assert body["task_runtime"]["enabled_task_count"] >= 7
    assert body["task_runtime"]["retrieval_backed_task_count"] == 2
    assert any(
        task["task_id"] == "knowledge_search.v1" and task["stubbed"] is False
        for task in body["task_runtime"]["tasks"]
    )
    assert body["safety_runtime"]["runtime_redaction_active"] is False
    assert body["safety_runtime"]["enforced_control_ids"] == [
        "response_labeling",
        "correlation_and_audit",
    ]
    assert body["safety_governance"]["governance_ready"] is False
    assert body["safety_governance"]["blocking_area_count"] == 3
    assert body["safety_governance"]["runtime_status"]["runtime_redaction_active"] is False
    assert body["safety_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["safety_governance"]["evidence_readiness"]["approval_gate"]["domain_id"] == (
        "safety_enforcement"
    )
    assert body["migration_contract_enforced"] is True
    assert body["startup_readiness_blocking"] is False
    assert body["prompt_count"] >= 3


def test_service_metadata_exposes_store_modes(client: TestClient) -> None:
    response = client.get("/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["auditStoreMode"] == "memory"
    assert body["promptStoreMode"] == "memory"
    assert body["retrievalStoreMode"] == "memory"
    assert body["startupReadinessPolicy"] == "warn"
    assert body["readinessProbePolicy"] == "observe"
