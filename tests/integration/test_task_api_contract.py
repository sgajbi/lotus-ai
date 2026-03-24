from pathlib import Path

from fastapi.testclient import TestClient
from _pytest.monkeypatch import MonkeyPatch

from app.main import app
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


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
    assert body["audit"]["prompt_selection"]["prompt_version"] == "foundation.explain.v1"
    assert body["audit"]["prompt_selection"]["latest_control_event"] is None
    assert body["audit"]["safety"]["safety_mode"] == "documented_only"
    assert body["audit"]["safety"]["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert body["audit"]["safety"]["disposition"] == "DOCUMENTED_ONLY"
    assert body["audit"]["safety"]["runtime_redaction_active"] is False
    assert len(body["evidence"]["descriptors"]) == 5
    assert body["evidence"]["descriptors"][0]["evidence_type"] == "task_contract"
    assert body["result"]["structured_output"]["caller_app"] == "lotus-manage"


def test_task_execute_contract_enforces_runtime_redaction_when_enabled(client: TestClient) -> None:
    from app.config import settings

    settings.safety_mode = "runtime_enforced"

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-456-redacted",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED", "violations": 2},
                "source_refs": ["lotus-manage:run:reb_003"],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["audit"]["safety"]["safety_mode"] == "runtime_enforced"
    assert body["audit"]["safety"]["disposition"] == "ENFORCED_REDACTED"
    assert (
        body["result"]["message"]
        == "Stub execution completed for foundation-phase task explain.v1."
    )
    assert "caller_app" not in body["result"]["structured_output"]
    assert "context_summary" not in body["result"]["structured_output"]
    assert "source_refs" not in body["result"]["structured_output"]

    settings.safety_mode = "documented_only"


def test_task_execute_contract_reflects_promoted_prompt_lineage(tmp_path: Path) -> None:
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    database_url = f"sqlite:///{tmp_path / 'task-contract-prompt-rollout.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
                get_evaluation_runtime_store().save_run(
                    EvaluationRunRecord(
                        run_id=f"runtime_task_prompt_gate_{fixture_id}",
                        fixture_id=fixture_id,
                        manifest_version="foundation.v1",
                        lifecycle_status="COMPLETED",
                        triggered_by="operator-a",
                        submitted_at="2026-03-24T09:00:00Z",
                        async_job_id=f"async_task_prompt_gate_{fixture_id}",
                        latest_message="Prompt rollout approval fixture passed.",
                        verdict="PASS",
                        case_count=1,
                    )
                )

            promote_response = durable_client.post(
                "/platform/prompts/control-actions",
                json={
                    "task_id": "explain.v1",
                    "action_type": "PROMOTE_CANDIDATE",
                    "candidate_prompt_version": "foundation.explain.v2",
                    "requested_by": "alice@lotus.test",
                    "approved_by": "bob@lotus.test",
                    "reason": "Promote reviewed prompt candidate",
                },
            )
            assert promote_response.status_code == 200

            response = durable_client.post(
                "/ai/tasks/execute",
                json={
                    "task_id": "explain.v1",
                    "input_mode": "STRUCTURED_CONTEXT",
                    "caller": {
                        "caller_app": "lotus-manage",
                        "correlation_id": "corr-456-promoted",
                        "requested_by": "ops.user@lotus",
                        "tenant_id": "tenant-sg-001",
                    },
                    "context": {
                        "summary": "Explain rebalance outcome",
                        "payload": {"status": "BLOCKED", "violations": 2},
                        "source_refs": ["lotus-manage:run:reb_005"],
                    },
                    "expected_output_label": "EXPLANATION_ONLY",
                },
            )

    body = response.json()
    prompt_evidence = next(
        descriptor
        for descriptor in body["evidence"]["descriptors"]
        if descriptor["evidence_type"] == "prompt_selection"
    )
    assert response.status_code == 200
    assert body["audit"]["prompt_version"] == "foundation.explain.v2"
    assert (
        body["audit"]["prompt_selection"]["previous_active_prompt_version"]
        == "foundation.explain.v1"
    )
    assert body["audit"]["prompt_selection"]["latest_control_event"]["action_type"] == (
        "PROMOTE_CANDIDATE"
    )
    assert prompt_evidence["attributes"]["prompt_version"] == "foundation.explain.v2"


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
    assert body["execution_status"] == "COMPLETED"
    assert body["caller_app"] == "lotus-advise"
    assert body["requested_by"] == "advisor.user@lotus"
    assert body["tenant_id"] == "tenant-us-002"
    assert body["category"] == "summarize"
    assert body["output_label"] == "DRAFT"
    assert body["prompt_version"] == "foundation.summarize.v1"
    assert body["prompt_selection"]["prompt_version"] == "foundation.summarize.v1"
    assert body["safety_mode"] == "documented_only"
    assert body["enforced_safety_controls"] == [
        "response_labeling",
        "correlation_and_audit",
    ]
    assert body["safety_outcome"]["disposition"] == "DOCUMENTED_ONLY"
    assert body["safety_outcome"]["runtime_redaction_active"] is False
    assert body["evidence"]["descriptors"][0]["evidence_type"] == "task_contract"
    assert body["structured_output"]["caller_app"] == "lotus-advise"


def test_task_execute_contract_returns_rejected_result_when_runtime_safety_blocks_output(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings
    from app.contracts.providers import ProviderExecutionResponse

    settings.safety_mode = "runtime_enforced"
    monkeypatch.setattr(
        "app.services.task_execution_pipeline.execute_text_generation",
        lambda _request: ProviderExecutionResponse(
            provider_id="text.stub",
            provider_mode="stub",
            stubbed=True,
            message="Unsafe raw payload.",
            structured_output={"raw_context": {"account_number": "12345"}},
        ),
    )

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-456-blocked",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED", "violations": 2},
                "source_refs": ["lotus-manage:run:reb_004"],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "REJECTED"
    assert body["audit"]["safety"]["disposition"] == "BLOCKED"
    assert body["result"]["structured_output"]["safety_blocked"] is True
    safety_evidence = next(
        descriptor
        for descriptor in body["evidence"]["descriptors"]
        if descriptor["evidence_type"] == "safety_outcome"
    )
    assert safety_evidence["attributes"]["disposition"] == "BLOCKED"

    request_id = body["audit"]["request_id"]
    audit_response = client.get(f"/ai/audit/{request_id}")
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["execution_status"] == "REJECTED"
    assert audit_body["safety_outcome"]["disposition"] == "BLOCKED"
    assert audit_body["evidence"]["descriptors"][3]["attributes"]["disposition"] == "BLOCKED"

    settings.safety_mode = "documented_only"


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
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-catalog-3",
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
                "source_refs": ["lotus-manage:knowledge-answer:catalog_1"],
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
    assert all(
        record["requested_by"] == "advisor.user@lotus" for record in identity_body["records"]
    )
    assert all(record["tenant_id"] == "tenant-us-002" for record in identity_body["records"])

    retrieval_filtered_response = client.get(
        "/ai/audit",
        params={
            "category": "knowledge_answer",
            "output_label": "RETRIEVAL_ANSWER",
            "limit": 10,
        },
    )

    assert retrieval_filtered_response.status_code == 200
    retrieval_body = retrieval_filtered_response.json()
    assert retrieval_body["filters_applied"] == {
        "limit": 10,
        "category": "knowledge_answer",
        "output_label": "RETRIEVAL_ANSWER",
    }
    assert retrieval_body["record_count"] >= 1
    assert all(record["category"] == "knowledge_answer" for record in retrieval_body["records"])
    assert all(record["output_label"] == "RETRIEVAL_ANSWER" for record in retrieval_body["records"])


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
    assert body["audit"]["prompt_selection"]["prompt_version"] == "foundation.knowledge_search.v1"
    assert body["result"]["structured_output"]["provider_id"] == "retrieval.catalog"
    assert body["result"]["structured_output"]["catalog_only"] is True
    assert body["result"]["structured_output"]["hit_count"] >= 1
    assert body["result"]["structured_output"]["citation_count"] >= 1
    assert body["result"]["structured_output"]["support_score"] >= 0.5
    assert body["result"]["structured_output"]["citations"][0]["source_id"] == "lotus-platform-rfcs"
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
    assert body["audit"]["prompt_selection"]["prompt_version"] == "foundation.knowledge_answer.v1"
    assert body["result"]["structured_output"]["provider_id"] == "retrieval.answer"
    assert body["result"]["structured_output"]["catalog_only"] is True
    assert body["result"]["structured_output"]["answer_mode"] == "CITATION_BACKED"
    assert body["result"]["structured_output"]["support_score"] >= 0.5
    assert body["result"]["structured_output"]["citations"][0]["source_id"] == "lotus-platform-rfcs"
    assert "Sources: lotus-platform-rfcs" in body["result"]["message"]


def test_task_execute_contract_refuses_low_support_knowledge_answer(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-knowledge-3",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": ["lotus-manage:knowledge-answer:003"],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "knowledge_answer.v1"
    assert body["result"]["structured_output"]["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT"
    assert body["result"]["structured_output"]["support_score"] < 0.75
    assert "Insufficient support" in body["result"]["message"]


def test_task_execute_contract_reports_live_retrieval_search_truthfully(
    client: TestClient,
) -> None:
    from app.config import settings
    from app.services.retrieval_store import get_retrieval_repository

    settings.retrieval_mode = "enabled"
    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-knowledge-live-1",
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
                "source_refs": ["lotus-manage:knowledge-search:live:001"],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["audit"]["provider_mode"] == "live_search"
    assert body["result"]["structured_output"]["provider_id"] == "retrieval.live_search"
    assert body["result"]["structured_output"]["provider_mode"] == "live_search"
    assert body["result"]["structured_output"]["execution_stage"] == "LIVE_SEARCH"
    assert body["result"]["structured_output"]["catalog_only"] is False
    retrieval_evidence = next(
        descriptor
        for descriptor in body["evidence"]["descriptors"]
        if descriptor["evidence_type"] == "retrieval_posture"
    )
    assert retrieval_evidence["attributes"]["request_execution_stage"] == "LIVE_SEARCH"
    assert retrieval_evidence["attributes"]["request_provider_mode"] == "live_search"
