from fastapi.testclient import TestClient


def test_task_execute_contract(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-456",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
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


def test_audit_record_route_returns_saved_execution(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "summarize.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": "corr-789",
                "requested_by": "advisor.user@lotus",
                "tenant_id": "tenant-us-002",
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
    body = audit_response.json()
    assert body["caller_app"] == "lotus-advise"
    assert body["requested_by"] == "advisor.user@lotus"
    assert body["tenant_id"] == "tenant-us-002"
    assert body["category"] == "summarize"
    assert body["output_label"] == "DRAFT"
    assert body["prompt_version"] == "foundation.summarize.v1"
    assert body["safety_mode"] == "documented_only"
    assert body["enforced_safety_controls"] == [
        "response_labeling",
        "correlation_and_audit",
    ]
    assert body["evidence"]["descriptors"][0]["evidence_type"] == "task_contract"
    assert body["structured_output"]["caller_app"] == "lotus-advise"


def test_audit_catalog_route_returns_filtered_records(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-catalog-1",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED"},
                "source_refs": ["lotus-manage:run:reb_catalog_1"],
            },
        },
    )
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "summarize.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": "corr-catalog-2",
                "requested_by": "advisor.user@lotus",
                "tenant_id": "tenant-us-002",
            },
            "context": {
                "summary": "Summarize proposal workflow",
                "payload": {"status": "PENDING_REVIEW"},
                "source_refs": ["lotus-advise:proposal:prop_catalog_1"],
            },
        },
    )

    response = client.get("/ai/audit", params={"caller_app": "lotus-advise", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["filters_applied"] == {"limit": 10, "caller_app": "lotus-advise"}
    assert body["record_count"] >= 1
    assert all(record["caller_app"] == "lotus-advise" for record in body["records"])

    identity_filtered_response = client.get(
        "/ai/audit",
        params={
            "requested_by": "advisor.user@lotus",
            "tenant_id": "tenant-us-002",
            "limit": 10,
        },
    )

    assert identity_filtered_response.status_code == 200
    identity_body = identity_filtered_response.json()
    assert identity_body["filters_applied"] == {
        "limit": 10,
        "requested_by": "advisor.user@lotus",
        "tenant_id": "tenant-us-002",
    }
    assert identity_body["record_count"] >= 1
    assert all(record["requested_by"] == "advisor.user@lotus" for record in identity_body["records"])
    assert all(record["tenant_id"] == "tenant-us-002" for record in identity_body["records"])


def test_audit_record_route_returns_not_found_for_unknown_request(client: TestClient) -> None:
    response = client.get("/ai/audit/missing_request_id")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No lotus-ai audit record found for request_id: missing_request_id"
    )


def test_task_execute_contract_supports_bounded_knowledge_search(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-knowledge-1",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Search Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": ["lotus-manage:knowledge-search:001"],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "knowledge_search.v1"
    assert body["category"] == "knowledge_search"
    assert body["output_label"] == "RETRIEVAL_ANSWER"
    assert body["audit"]["stubbed"] is False
    assert body["audit"]["provider_mode"] == "catalog_only"
    assert body["audit"]["prompt_version"] == "foundation.knowledge_search.v1"
    assert body["result"]["structured_output"]["provider_id"] == "retrieval.catalog"
    assert body["result"]["structured_output"]["catalog_only"] is True
    assert body["result"]["structured_output"]["hit_count"] >= 1
    assert body["result"]["structured_output"]["hits"][0]["source_id"] == "lotus-platform-rfcs"


def test_task_execute_contract_supports_bounded_knowledge_answer(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-knowledge-2",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": ["lotus-manage:knowledge-answer:001"],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "knowledge_answer.v1"
    assert body["category"] == "knowledge_answer"
    assert body["output_label"] == "RETRIEVAL_ANSWER"
    assert body["audit"]["stubbed"] is False
    assert body["audit"]["provider_mode"] == "catalog_answer"
    assert body["audit"]["prompt_version"] == "foundation.knowledge_answer.v1"
    assert body["result"]["structured_output"]["provider_id"] == "retrieval.answer"
    assert body["result"]["structured_output"]["catalog_only"] is True
    assert body["result"]["structured_output"]["citations"][0] == "lotus-platform-rfcs"
    assert "Sources: lotus-platform-rfcs" in body["result"]["message"]
