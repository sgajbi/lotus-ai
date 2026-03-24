from fastapi.testclient import TestClient


def test_observability_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/observability/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["domain_count"] == 6
    assert body["unavailable_domain_count"] == 0
    assert body["incident_evidence_supported_domain_count"] >= 1
    assert any(domain["domain_id"] == "provider" for domain in body["domains"])
    assert any(domain["domain_id"] == "safety" for domain in body["domains"])
    assert any(
        item["evidence_id"] == "safety_runtime_enforcement_state"
        for item in body["incident_evidence_items"]
    )


def test_observability_governance_routes(client: TestClient) -> None:
    activation_response = client.get("/platform/observability/activation-readiness")
    assert activation_response.status_code == 200
    activation_body = activation_response.json()
    assert activation_body["activation_ready"] is False
    assert activation_body["domain_count"] == 6

    runbook_response = client.get("/platform/observability/runbook-readiness")
    assert runbook_response.status_code == 200
    runbook_body = runbook_response.json()
    assert runbook_body["runbook_ready"] is True
    assert runbook_body["required_item_count"] == 3

    governance_response = client.get("/platform/observability/governance-status")
    assert governance_response.status_code == 200
    governance_body = governance_response.json()
    assert governance_body["governance_ready"] is False
    assert governance_body["activation_readiness"]["activation_ready"] is False
    assert governance_body["runbook_readiness"]["runbook_ready"] is True
    assert governance_body["runtime_status"]["domain_count"] == 6


def test_observability_incident_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/incident-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["domain_count"] == 6
    assert any(summary["domain_id"] == "provider" for summary in body["summaries"])
    assert any(summary["domain_id"] == "retrieval" for summary in body["summaries"])
    assert any(summary["domain_id"] == "async" for summary in body["summaries"])
    assert any(summary["domain_id"] == "evaluation" for summary in body["summaries"])
    assert any(summary["domain_id"] == "prompt" for summary in body["summaries"])
    assert any(summary["domain_id"] == "safety" for summary in body["summaries"])


def test_provider_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/provider-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "provider"
    assert body["telemetry"]["incident_evidence_supported"] is True
    assert body["incident_evidence_items"][0]["evidence_id"] == "provider_operations_incident_state"


def test_evaluation_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/evaluation-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "evaluation"
    assert body["incident_evidence_items"][0]["evidence_id"] == "evaluation_approval_gate_state"


def test_prompt_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/prompt-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "prompt"
    assert body["incident_evidence_items"][0]["evidence_id"] == "prompt_rollout_approval_state"


def test_safety_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/safety-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "safety"
    assert body["incident_evidence_items"][0]["evidence_id"] == "safety_runtime_enforcement_state"


def test_observability_breakdown_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-observe-breakdown-1",
                "tenant_id": "tenant-sg-001",
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
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": "corr-observe-breakdown-2",
                "tenant_id": "tenant-us-002",
            },
            "context": {
                "summary": "Explain portfolio state",
                "payload": {"status": "OK"},
                "source_refs": [],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    response = client.get("/platform/observability/breakdowns", params={"limit": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["sampled_audit_record_limit"] == 50
    assert body["sampled_audit_record_count"] >= 2
    assert any(sample["caller_app"] == "lotus-manage" for sample in body["caller_apps"])
    assert any(sample["tenant_id"] == "tenant-sg-001" for sample in body["tenants"])
    assert any(
        sample["capability_kind"] == "TASK" and sample["capability_id"] == "knowledge_answer.v1"
        for sample in body["capabilities"]
    )
