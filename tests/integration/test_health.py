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
    assert body["provider_governance"]["blocking_area_count"] == 3
    assert body["provider_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["provider_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["provider_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["retrieval_governance"]["governance_ready"] is False
    assert body["retrieval_governance"]["blocking_area_count"] == 3
    assert body["retrieval_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["retrieval_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["retrieval_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["prompt_governance"]["governance_ready"] is False
    assert body["prompt_governance"]["blocking_area_count"] == 3
    assert body["prompt_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["prompt_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["prompt_governance"]["evidence_readiness"]["evidence_ready"] is False
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


def test_service_metadata_exposes_store_modes(client: TestClient) -> None:
    response = client.get("/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["auditStoreMode"] == "memory"
    assert body["promptStoreMode"] == "memory"
    assert body["retrievalStoreMode"] == "memory"
    assert body["startupReadinessPolicy"] == "warn"
    assert body["readinessProbePolicy"] == "observe"


