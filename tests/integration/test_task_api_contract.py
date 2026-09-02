from pathlib import Path

from fastapi.testclient import TestClient
from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.main import app
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.governed_control import promote_prompt_for_test


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
    assert body["audit"]["provider_id"] == "text.stub"
    assert body["audit"]["adapter_kind"] == "STUB"
    assert body["audit"]["model_id"] is None
    assert body["audit"]["prompt_version"] == "foundation.explain.v1"
    assert body["audit"]["prompt_selection"]["prompt_version"] == "foundation.explain.v1"
    assert body["audit"]["prompt_selection"]["latest_control_event"] is None
    assert body["audit"]["safety"]["safety_mode"] == "documented_only"
    assert body["audit"]["safety"]["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert body["audit"]["safety"]["disposition"] == "DOCUMENTED_ONLY"
    assert body["audit"]["safety"]["runtime_redaction_active"] is True
    assert body["audit"]["authorization"]["outcome"] == "ALLOWED"
    assert len(body["evidence"]["descriptors"]) == 8
    validation_evidence = body["evidence"]["descriptors"][-1]
    assert validation_evidence["evidence_type"] == "output_validation"
    assert validation_evidence["attributes"]["validation_state"] == "VALIDATED"
    assert validation_evidence["attributes"]["authority"] == "non_authoritative_ai_output"
    assert body["evidence"]["descriptors"][0]["evidence_type"] == "task_contract"
    assert body["evidence"]["descriptors"][3]["evidence_type"] == "routing_decision"
    routing_attributes = body["evidence"]["descriptors"][3]["attributes"]
    assert routing_attributes["policy_id"] == "fixed_configured_mode"
    assert routing_attributes["selected_provider_id"] == "text.stub"
    assert body["audit"]["routing_decision"]["selected_provider_id"] == "text.stub"
    assert body["evidence"]["descriptors"][6]["evidence_type"] == "access_control"
    assert body["result"]["structured_output"]["caller_app"] == "lotus-manage"


def test_task_execute_contract_returns_grounded_advisor_brief_for_gateway_fact_bundle(
    client: TestClient,
) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-gateway",
                "correlation_id": "corr-advisor-brief-001",
            },
            "context": {
                "summary": "Draft advisor brief from source performance facts.",
                "payload": {
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [
                        {"key": "portfolio_context", "value": "ready"},
                        {"key": "performance_context", "value": "ready"},
                    ],
                    "contribution": {
                        "top_positions": [
                            {"position_id": "AAPL US", "total_contribution_pct": 0.3}
                        ],
                    },
                    "attribution": {
                        "top_effects": [
                            {"key_label": "Asset Class / Equity", "total_effect_pct": -4.1},
                        ],
                    },
                },
                "source_refs": [
                    "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
                    "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-details:YTD",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "explain.v1"
    assert body["status"] == "COMPLETED"
    assert body["audit"]["stubbed"] is True
    assert body["audit"]["authorization"]["caller_app"] == "lotus-gateway"
    assert body["result"]["message"] == (
        "PB_SG_GLOBAL_BAL_001 delivered 1.25% over YTD versus 7.93% for the benchmark, "
        "resulting in -6.68% active return. net flow was N/A and ending market value "
        "was N/A. largest contribution came from AAPL US (0.30%). largest benchmark-relative "
        "attribution effect was Asset Class / Equity (-4.10%)."
    )
    assert body["result"]["structured_output"]["advisor_brief_status"] == "ready"
    assert body["result"]["structured_output"]["talking_points"][0] == {
        "headline": "YTD active return was -6.68%.",
        "detail": (
            "Portfolio Return was 1.25% versus Benchmark Return 7.93%. Review Return "
            "Path for period-by-period context."
        ),
        "tone": "warning",
        "evidence_refs": [
            {
                "metric_label": "Active Return",
                "metric_value": "-6.68%",
                "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
            }
        ],
    }
    assert body["result"]["structured_output"]["recommended_actions"][0]["label"] == (
        "Review Return Path"
    )
    assert body["result"]["structured_output"]["grounded_facts"][0] == {
        "metric_label": "Portfolio Return",
        "metric_value": "1.25%",
        "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
    }
    assert body["result"]["structured_output"]["source_refs"] == [
        "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-details:YTD",
    ]
    assert len(body["evidence"]["descriptors"]) == 8
    validation_evidence = body["evidence"]["descriptors"][-1]
    assert validation_evidence["evidence_type"] == "output_validation"
    assert validation_evidence["attributes"]["validation_state"] == "VALIDATED"
    assert validation_evidence["attributes"]["authority"] == "non_authoritative_ai_output"


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

            # Promotion is governed (issue #157): setup runs the two-step
            # flow in process, since header trust cannot approve anything.
            promote_prompt_for_test(
                task_id="explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                reason="Promote reviewed prompt candidate",
            )

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


def test_audit_record_route_returns_saved_execution(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)

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
    assert body["provider_mode"] == "disabled"
    assert body["provider_id"] == "text.stub"
    assert body["adapter_kind"] == "STUB"
    assert body["model_id"] is None
    assert body["safety_mode"] == "documented_only"
    assert body["enforced_safety_controls"] == [
        "response_labeling",
        "correlation_and_audit",
        "runtime_redaction_engine",
    ]
    assert body["safety_outcome"]["disposition"] == "DOCUMENTED_ONLY"
    assert body["safety_outcome"]["runtime_redaction_active"] is True
    assert body["authorization"]["outcome"] == "ALLOWED"
    assert body["evidence"]["descriptors"][0]["evidence_type"] == "task_contract"
    assert body["structured_output"]["caller_app"] == "lotus-advise"


def test_task_execute_contract_returns_rejected_result_when_runtime_safety_blocks_output(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.contracts.providers import ProviderExecutionResponse

    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
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
    # This test stubs execute_text_generation itself, so the real gateway never
    # ran and no routing decision exists - the record must say so honestly.
    assert audit_body["routing_decision"] is None
    assert audit_body["evidence"]["descriptors"][3]["attributes"]["disposition"] == "BLOCKED"

    settings.safety_mode = "documented_only"


def test_audit_catalog_route_returns_filtered_records(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)

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
    assert body["filters_applied"] == {
        "limit": 10,
        "tenant_scope": "ALL_TENANTS",
        "caller_app": "lotus-advise",
    }
    assert body["record_count"] >= 1
    assert all(record["caller_app"] == "lotus-advise" for record in body["records"])

    rejected_tenant_filter_response = client.get(
        "/ai/audit",
        params={
            "tenant_id": "tenant-us-002",
            "limit": 10,
        },
    )

    assert rejected_tenant_filter_response.status_code == 422

    identity_filtered_response = client.get(
        "/ai/audit",
        params={"requested_by": "advisor.user@lotus", "limit": 10},
        headers={"X-Caller-App": "lotus-advise"},
    )

    assert identity_filtered_response.status_code == 200
    identity_body = identity_filtered_response.json()
    assert identity_body["filters_applied"] == {
        "limit": 10,
        "tenant_scope": "RESTRICTED_TENANTS",
        "requested_by": "advisor.user@lotus",
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
        "tenant_scope": "ALL_TENANTS",
        "category": "knowledge_answer",
        "output_label": "RETRIEVAL_ANSWER",
    }
    assert retrieval_body["record_count"] >= 1
    assert all(record["category"] == "knowledge_answer" for record in retrieval_body["records"])
    assert all(record["output_label"] == "RETRIEVAL_ANSWER" for record in retrieval_body["records"])


def test_audit_record_route_returns_not_found_for_unknown_request(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)

    response = client.get("/ai/audit/missing_request_id")

    assert response.status_code == 404
    assert (
        response.json()["detail"] == "No lotus-ai audit record found for the requested identifier."
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


def test_task_execute_contract_blocks_unknown_caller(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "unknown-app",
                "correlation_id": "corr-unknown",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED"},
                "source_refs": [],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 403
    assert "not registered" in response.json()["detail"]


def test_task_execute_contract_blocks_unauthorized_retrieval_source(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-workbench",
                "correlation_id": "corr-source-blocked",
            },
            "context": {
                "summary": "Search Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-standards"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    assert response.status_code == 403
    assert "approved policy scope" in response.json()["detail"]


def test_task_execute_contract_blocks_live_provider_for_caller_without_live_permission(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_live_unauthorized",
            "model": "gpt-5.4",
            "output_text": "Live explanation response.",
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        },
    )

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": "corr-live-unauthorized",
                "tenant_id": "tenant-us-002",
            },
            "context": {
                "summary": "Explain advisory posture",
                "payload": {"status": "PENDING_REVIEW"},
                "source_refs": [],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 403
    assert "not authorized for live provider execution" in response.json()["detail"]


def test_task_execute_contract_allows_lotus_gateway_live_advisor_brief(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_gateway_advisor_brief",
            "model": "gpt-5.4",
            "output_text": (
                '{"grounded_summary":"Portfolio lagged benchmark on YTD.",'
                '"talking_points":[],"recommended_actions":[],"risks_and_exceptions":[]}'
            ),
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        },
    )

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-gateway",
                "correlation_id": "corr-live-gateway-advisor",
            },
            "context": {
                "summary": "Generate Advisor Brief",
                "payload": {
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [
                        {"label": "Advisor Brief", "value": "Ready"},
                    ],
                },
                "source_refs": [
                    "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["audit"]["provider_mode"] == "openai"
    assert body["audit"]["provider_id"] == "text.openai"
    assert body["audit"]["adapter_kind"] == "OPENAI_LIVE"
    assert body["audit"]["model_id"] == "gpt-5.4"
    assert body["result"]["structured_output"]["grounded_summary"] == (
        "Portfolio lagged benchmark on YTD."
    )


def test_task_execute_contract_supports_local_openai_compatible_execution(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_input_cost_per_1k_tokens = 0.0
    settings.live_text_output_cost_per_1k_tokens = 0.0
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {
                "endpoint_reachable": True,
                "model_available": True,
                "blocking_reason": None,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_local_contract_001",
            "model": "qwen3:8b",
            "output_text": "Local governed explanation response.",
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        },
    )

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-local-contract",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED", "violations": 2},
                "source_refs": ["lotus-manage:run:reb_local_contract"],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["audit"]["stubbed"] is False
    assert body["audit"]["provider_mode"] == "local_openai_compatible"
    assert body["audit"]["provider_id"] == "text.local"
    assert body["audit"]["adapter_kind"] == "OPENAI_COMPATIBLE_LOCAL"
    assert body["audit"]["model_id"] == "qwen3:8b"
    assert body["result"]["message"] == "Local governed explanation response."
    provider_evidence = next(
        descriptor
        for descriptor in body["evidence"]["descriptors"]
        if descriptor["evidence_type"] == "provider_resolution"
    )
    assert provider_evidence["attributes"]["provider_id"] == "text.local"
    assert provider_evidence["attributes"]["adapter_kind"] == "OPENAI_COMPATIBLE_LOCAL"
    assert provider_evidence["attributes"]["model_id"] == "qwen3:8b"


def test_task_execute_contract_guards_against_local_contract_echo_output(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen2.5:1.5b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_input_cost_per_1k_tokens = 0.0
    settings.live_text_output_cost_per_1k_tokens = 0.0
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {
                "endpoint_reachable": True,
                "model_available": True,
                "blocking_reason": None,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_local_contract_echo",
            "model": "qwen2.5:1.5b",
            "output_text": (
                '{"grounded_summary":"The output contract for the structured Lotus domain with '
                'the provided data and context is as follows.",'
                '"talking_points":[],"recommended_actions":[],"risks_and_exceptions":[]}'
            ),
            "usage": {"input_tokens": 220, "output_tokens": 80, "total_tokens": 300},
        },
    )

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-gateway",
                "correlation_id": "corr-local-echo-guardrail",
            },
            "context": {
                "summary": "Generate Advisor Brief",
                "payload": {
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [
                        {"label": "Advisor Brief", "value": "Ready"},
                    ],
                    "contribution": {
                        "top_positions": [{"position_id": "AAPL US", "total_contribution_pct": 0.3}]
                    },
                },
                "source_refs": [
                    "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["audit"]["provider_mode"] == "local_openai_compatible"
    assert body["audit"]["model_id"] == "qwen2.5:1.5b"
    assert body["result"]["message"].startswith("PB SG GLOBAL BAL 001 delivered 1.25% over YTD")
    assert body["result"]["structured_output"]["advisor_brief_guardrail_triggered"] is True
    assert body["result"]["structured_output"]["advisor_brief_guardrail_reason"] == (
        "invalid_grounded_summary_language"
    )
    assert body["result"]["structured_output"]["talking_points"]


def test_declared_capability_requirements_ride_the_response_visibly_unenforced(
    client: TestClient,
) -> None:
    """Issue #244 S1 at the HTTP boundary: a consumer declares what the
    workload needs — never a provider or a vendor feature — and the response
    shows the declaration recorded with an explicit NOT_ENFORCED posture, so
    nobody can mistake a recorded ceiling for a held one."""

    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-requirements-http",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED"},
                "source_refs": ["lotus-manage:run:reb_http_1"],
            },
            "requirements": {
                "structured_output_required": True,
                "max_latency_ms": 2000,
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )

    assert response.status_code == 200
    body = response.json()
    descriptor = next(
        d
        for d in body["evidence"]["descriptors"]
        if d["evidence_type"] == "capability_requirements"
    )
    assert descriptor["attributes"]["requirements_enforcement"] == "NOT_ENFORCED"
    assert descriptor["attributes"]["declared"] == {
        "structured_output_required": True,
        "max_latency_ms": 2000,
    }

    empty = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {"caller_app": "lotus-manage", "correlation_id": "corr-req-empty"},
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED"},
                "source_refs": ["lotus-manage:run:reb_http_2"],
            },
            "requirements": {},
        },
    )
    assert empty.status_code == 422
