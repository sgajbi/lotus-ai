from pathlib import Path
from typing import cast

from fastapi import HTTPException
from pytest import MonkeyPatch, raises
from pytest_mock import MockerFixture

from app.contracts.access_control import AuthorizationOutcome
from app.contracts.audit import AuditRecordResponse
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.contracts.providers import ProviderExecutionResponse
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.contracts.prompts import PromptControlActionRequest, PromptControlActionType
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.prompt_rollout_control import apply_prompt_control_action
from app.services.task_executor import execute_task
from app.services.workflow_pack_run_ledger import WorkflowPackRunStoreUnavailableError
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def _request(
    task_id: str, expected_output_label: OutputLabel | None = None
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_id=task_id,
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(
            caller_app="lotus-manage",
            correlation_id="corr-123",
            tenant_id="tenant-sg-001",
        ),
        context=TaskContextEnvelope(
            summary="Explain rebalance outcome",
            payload={"status": "BLOCKED", "rule_count": 3},
            source_refs=["lotus-manage:run:reb_001"],
        ),
        expected_output_label=expected_output_label,
    )


def test_execute_task_returns_stubbed_completed_response() -> None:
    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == "COMPLETED"
    assert response.task_id == "explain.v1"
    assert response.result.structured_output["phase"] == "foundation"
    assert response.result.structured_output["provider_id"] == "text.stub"
    assert response.result.structured_output["context_keys"] == ["rule_count", "status"]
    assert response.result.structured_output["output_label"] == "EXPLANATION_ONLY"
    assert response.result.structured_output["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert response.audit.stubbed is True
    assert response.audit.provider_id == "text.stub"
    assert response.audit.adapter_kind is not None
    assert response.audit.adapter_kind.value == "STUB"
    assert response.audit.model_id is None
    assert response.audit.prompt_version == "foundation.explain.v1"
    assert response.audit.prompt_selection.prompt_version == "foundation.explain.v1"
    assert response.audit.prompt_selection.latest_control_event is None
    assert response.audit.safety.safety_mode == "documented_only"
    assert response.audit.safety.redaction_posture == "MINIMIZATION_REQUIRED"
    assert response.audit.safety.disposition == "DOCUMENTED_ONLY"
    # The deterministic redaction engine enforces in every safety mode
    # (issue #150 slice 2).
    assert response.audit.safety.runtime_redaction_active is True
    assert response.audit.safety.enforced_controls == [
        "response_labeling",
        "correlation_and_audit",
        "runtime_redaction_engine",
    ]
    assert response.audit.safety.control_results[-1].control_id == "runtime_redaction_engine"
    assert len(response.evidence.descriptors) == 8
    assert response.evidence.descriptors[0].evidence_type == "task_contract"
    assert response.evidence.descriptors[1].evidence_type == "prompt_selection"
    assert response.evidence.descriptors[3].evidence_type == "routing_decision"
    routing_attributes = response.evidence.descriptors[3].attributes
    assert routing_attributes["policy_id"] == "fixed_configured_mode"
    assert routing_attributes["strategy"] == "FIXED"
    assert routing_attributes["selected_provider_id"] == "text.stub"
    routing_candidates = routing_attributes["candidates"]
    assert isinstance(routing_candidates, list)
    assert [c["provider_id"] for c in routing_candidates] == ["text.stub"]
    assert response.audit.routing_decision is not None
    assert response.audit.routing_decision.selected_provider_id == "text.stub"
    assert response.audit.authorization.outcome == AuthorizationOutcome.ALLOWED
    assert response.evidence.descriptors[6].evidence_type == "access_control"
    # The verdict rides a real end-to-end execution's evidence bundle, which is
    # what carries it to the run record and every projection built from it
    # (issue #231).
    assert response.evidence.descriptors[7].evidence_type == "output_validation"
    assert response.evidence.descriptors[7].attributes["validation_state"] == "VALIDATED"
    assert response.evidence.descriptors[7].attributes["authority"] == "non_authoritative_ai_output"


def test_execute_task_enforces_runtime_redaction_for_provider_backed_output() -> None:
    from app.config import settings

    settings.safety_mode = "runtime_enforced"

    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.audit.safety.safety_mode == "runtime_enforced"
    assert response.audit.safety.disposition == "ENFORCED_REDACTED"
    # Issue #150 slice 2: the deterministic redaction engine enforces
    # alongside key minimization.
    assert response.audit.safety.runtime_redaction_active is True
    assert "structured_output_key_minimization" in response.audit.safety.enforced_controls
    assert "runtime_redaction_engine" in response.audit.safety.enforced_controls
    assert (
        response.result.message == "Stub execution completed for foundation-phase task explain.v1."
    )
    assert "caller_app" not in response.result.structured_output
    assert "context_summary" not in response.result.structured_output
    assert "source_refs" not in response.result.structured_output
    assert response.result.structured_output["context_keys"] == ["rule_count", "status"]

    settings.safety_mode = "documented_only"


def test_execute_task_rejects_unknown_task() -> None:
    try:
        execute_task(_request("unknown.v1"))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "Unknown lotus-ai task_id" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown task")


def test_execute_task_rejects_output_label_mismatch() -> None:
    try:
        execute_task(_request("explain.v1", expected_output_label=OutputLabel.DRAFT))
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Expected output label does not match task configuration" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for output label mismatch")


def test_execute_task_blocks_unknown_caller() -> None:
    try:
        execute_task(
            TaskExecutionRequest(
                task_id="explain.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(caller_app="unknown-app", correlation_id="corr-unknown"),
                context=TaskContextEnvelope(
                    summary="Explain rebalance outcome",
                    payload={"status": "BLOCKED"},
                    source_refs=[],
                ),
                expected_output_label=OutputLabel.EXPLANATION_ONLY,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "not registered" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown caller")


def test_execute_task_blocks_restricted_tenant_mismatch() -> None:
    try:
        execute_task(
            TaskExecutionRequest(
                task_id="explain.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-manage",
                    correlation_id="corr-tenant-mismatch",
                    tenant_id="tenant-us-002",
                ),
                context=TaskContextEnvelope(
                    summary="Explain rebalance outcome",
                    payload={"status": "BLOCKED"},
                    source_refs=[],
                ),
                expected_output_label=OutputLabel.EXPLANATION_ONLY,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "not authorized" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for tenant mismatch")


def test_execute_task_persists_sorted_audit_context_keys(mocker: MockerFixture) -> None:
    audit_store = mocker.Mock()
    mocker.patch("app.services.task_execution_pipeline.get_audit_store", return_value=audit_store)

    execute_task(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-123",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Explain rebalance outcome",
                payload={"zeta": 1, "alpha": 2},
                source_refs=["lotus-manage:run:reb_001"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )

    audit_record = cast(AuditRecordResponse, audit_store.save.call_args.args[0])
    assert audit_record.execution_status == "COMPLETED"
    assert audit_record.context_keys == ["alpha", "zeta"]
    assert audit_record.caller_app == "lotus-manage"
    assert audit_record.correlation_id == "corr-123"
    assert audit_record.prompt_version == "foundation.explain.v1"
    assert audit_record.authorization.outcome == AuthorizationOutcome.ALLOWED


def test_execute_task_blocks_pack_backed_execution_before_audit_when_run_store_unavailable(
    mocker: MockerFixture,
) -> None:
    resolve_task_execution_mock = mocker.patch("app.services.task_executor.resolve_task_execution")
    persist_task_execution_audit_mock = mocker.patch(
        "app.services.task_executor.persist_task_execution_audit"
    )
    mocker.patch(
        "app.services.task_executor.ensure_workflow_pack_run_store_ready",
        side_effect=WorkflowPackRunStoreUnavailableError(
            "Workflow-pack run store is not ready. Current status is `MIGRATION_REQUIRED`."
        ),
    )

    try:
        execute_task(
            TaskExecutionRequest(
                task_id="explain.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-gateway",
                    correlation_id="corr-pack-preflight-001",
                ),
                context=TaskContextEnvelope(
                    summary="Draft advisor brief from source performance facts.",
                    payload={
                        "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                        "period": {"period": "YTD"},
                        "performance": {
                            "portfolio_return_pct": 1.25,
                            "benchmark_return_pct": 7.93,
                            "active_return_pct": -6.68,
                        },
                        "supportability": [{"key": "portfolio_context", "value": "ready"}],
                    },
                    source_refs=["lotus-gateway:performance-summary:YTD"],
                ),
                expected_output_label=OutputLabel.EXPLANATION_ONLY,
            )
        )
    except WorkflowPackRunStoreUnavailableError as exc:
        assert "MIGRATION_REQUIRED" in str(exc)
    else:
        raise AssertionError("Expected workflow-pack run store preflight to block execution")

    resolve_task_execution_mock.assert_not_called()
    persist_task_execution_audit_mock.assert_not_called()


def test_execute_task_runs_bounded_knowledge_search() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-ks-123",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-search:001"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.task_id == "knowledge_search.v1"
    assert response.output_label == OutputLabel.RETRIEVAL_ANSWER
    assert response.audit.stubbed is False
    assert response.audit.prompt_version == "foundation.knowledge_search.v1"
    assert response.audit.provider_mode == "catalog_only"
    assert response.result.structured_output["provider_id"] == "retrieval.catalog"
    assert response.result.structured_output["provider_mode"] == "catalog_only"
    assert response.result.structured_output["catalog_only"] is True
    assert response.result.structured_output["execution_stage"] == "CATALOG_ONLY"
    assert response.result.structured_output["query"] == "shared ai platform service"
    assert response.result.structured_output["hit_count"] >= 1
    assert response.result.structured_output["citation_count"] >= 1
    assert response.result.structured_output["support_score"] >= 0.5
    assert response.result.structured_output["citations"][0]["source_id"] == "lotus-platform-rfcs"
    assert (
        response.result.structured_output["citations"][0]["document_id"]
        == "lotus-platform-rfc-0069"
    )
    assert response.result.structured_output["hits"][0]["source_id"] == "lotus-platform-rfcs"


def test_execute_task_rejects_invalid_knowledge_search_payload() -> None:
    try:
        execute_task(
            TaskExecutionRequest(
                task_id="knowledge_search.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-manage",
                    correlation_id="corr-ks-124",
                    tenant_id="tenant-sg-001",
                ),
                context=TaskContextEnvelope(
                    summary="Search Lotus knowledge sources",
                    payload={"query": "", "limit": 3},
                    source_refs=[],
                ),
                expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "context.payload.query" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for invalid knowledge-search payload")


def test_execute_task_blocks_knowledge_search_for_unapproved_source() -> None:
    try:
        execute_task(
            TaskExecutionRequest(
                task_id="knowledge_search.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-workbench",
                    correlation_id="corr-ks-unauthorized-source",
                ),
                context=TaskContextEnvelope(
                    summary="Search Lotus knowledge sources",
                    payload={
                        "query": "shared ai platform service",
                        "source_ids": ["lotus-platform-standards"],
                        "limit": 3,
                    },
                    source_refs=[],
                ),
                expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "outside its approved policy scope" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unauthorized retrieval source")


def test_execute_task_runs_bounded_knowledge_answer() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-ka-123",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-answer:001"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.task_id == "knowledge_answer.v1"
    assert response.output_label == OutputLabel.RETRIEVAL_ANSWER
    assert response.audit.stubbed is False
    assert response.audit.prompt_version == "foundation.knowledge_answer.v1"
    assert response.audit.provider_mode == "catalog_answer"
    assert response.result.structured_output["provider_id"] == "retrieval.answer"
    assert response.result.structured_output["catalog_only"] is True
    assert response.result.structured_output["execution_stage"] == "CATALOG_ONLY"
    assert response.result.structured_output["hit_count"] >= 1
    assert response.result.structured_output["answer_mode"] == "CITATION_BACKED"
    assert response.result.structured_output["support_score"] >= 0.5
    assert response.result.structured_output["citations"][0]["source_id"] == "lotus-platform-rfcs"
    assert "Sources: lotus-platform-rfcs:lotus-platform-rfc-0069" in response.result.message


def test_execute_task_refuses_low_support_knowledge_answer() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-ka-124",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
                payload={
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-answer:002"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.result.structured_output["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT"
    assert response.result.structured_output["support_score"] < 0.75
    assert "Insufficient support" in response.result.message


def test_execute_task_routes_knowledge_search_through_live_retrieval(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.retrieval_mode = "enabled"
    repository = InMemoryRetrievalRepository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )
    monkeypatch.setattr(
        "app.services.retrieval_service.get_retrieval_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.services.retrieval_gateway.get_retrieval_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.retrieval.document_governance.get_retrieval_repository",
        lambda: repository,
    )

    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-ks-live-001",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-search:live:001"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.audit.provider_mode == "live_search"
    assert response.result.structured_output["provider_id"] == "retrieval.live_search"
    assert response.result.structured_output["catalog_only"] is False
    assert response.result.structured_output["execution_stage"] == "LIVE_SEARCH"
    assert response.result.structured_output["hits"][0]["document_id"] == "lotus-platform-rfc-0069"


def test_execute_task_enforces_runtime_redaction_for_retrieval_backed_output(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.retrieval_mode = "enabled"
    settings.safety_mode = "runtime_enforced"
    repository = InMemoryRetrievalRepository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )
    monkeypatch.setattr(
        "app.services.retrieval_service.get_retrieval_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.services.retrieval_gateway.get_retrieval_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.retrieval.document_governance.get_retrieval_repository",
        lambda: repository,
    )

    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-ks-safe-001",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-search:safe:001"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.audit.safety.safety_mode == "runtime_enforced"
    # Issue #150 slice 2: the deterministic redaction engine enforces
    # alongside key minimization.
    assert response.audit.safety.runtime_redaction_active is True
    assert "structured_output_key_minimization" in response.audit.safety.enforced_controls
    assert "runtime_redaction_engine" in response.audit.safety.enforced_controls
    assert "caller_app" not in response.result.structured_output
    assert response.result.structured_output["citation_count"] >= 1
    assert response.result.structured_output["hits"][0]["source_id"] == "lotus-platform-rfcs"

    settings.safety_mode = "documented_only"


def test_execute_task_returns_rejected_response_and_persists_audit_when_safety_blocks_output(
    mocker: MockerFixture,
) -> None:
    from app.config import settings

    settings.safety_mode = "runtime_enforced"
    audit_store = mocker.Mock()
    mocker.patch("app.services.task_execution_pipeline.get_audit_store", return_value=audit_store)
    mocker.patch(
        "app.services.task_execution_pipeline.execute_text_generation",
        return_value=ProviderExecutionResponse(
            provider_id="text.stub",
            provider_mode="stub",
            stubbed=True,
            message="Unsafe raw payload.",
            structured_output={"raw_context": {"account_number": "12345"}},
        ),
    )

    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == "REJECTED"
    assert response.audit.safety.disposition == "BLOCKED"
    assert response.result.structured_output["safety_blocked"] is True
    audit_record = cast(AuditRecordResponse, audit_store.save.call_args.args[0])
    assert audit_record.execution_status == "REJECTED"
    assert audit_record.safety_outcome.disposition == "BLOCKED"
    # execute_text_generation is stubbed at the pipeline seam here, so the real
    # gateway never ran and no routing decision exists - the record says so.
    assert audit_record.routing_decision is None
    assert audit_record.evidence.descriptors[3].attributes["disposition"] == "BLOCKED"

    settings.safety_mode = "documented_only"


def test_execute_task_rejects_live_knowledge_search_when_searchable_corpus_is_unavailable(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.config import settings

    settings.retrieval_mode = "enabled"
    repository = InMemoryRetrievalRepository()
    monkeypatch.setattr(
        "app.services.retrieval_service.get_retrieval_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.services.retrieval_gateway.get_retrieval_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        "app.retrieval.document_governance.get_retrieval_repository",
        lambda: repository,
    )

    try:
        execute_task(
            TaskExecutionRequest(
                task_id="knowledge_search.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-manage",
                    correlation_id="corr-ks-live-blocked-001",
                    tenant_id="tenant-sg-001",
                ),
                context=TaskContextEnvelope(
                    summary="Search Lotus knowledge sources",
                    payload={
                        "query": "shared ai platform service",
                        "source_ids": ["lotus-platform-rfcs"],
                        "limit": 3,
                    },
                    source_refs=["lotus-manage:knowledge-search:live:blocked:001"],
                ),
                expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "indexing is still pending" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException when live searchable corpus is unavailable")


def test_execute_task_routes_allowlisted_task_through_live_provider(
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
            "id": "resp_live_001",
            "model": "gpt-5.4",
            "output_text": "Live explanation response.",
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        },
    )

    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == "COMPLETED"
    assert response.audit.stubbed is False
    assert response.audit.provider_mode == "openai"
    assert response.audit.provider_id == "text.openai"
    assert response.audit.adapter_kind is not None
    assert response.audit.adapter_kind.value == "OPENAI_LIVE"
    assert response.audit.model_id == "gpt-5.4"
    assert response.result.message == "Live explanation response."
    assert response.result.structured_output["provider_id"] == "text.openai"
    assert response.result.structured_output["model_id"] == "gpt-5.4"
    assert response.result.structured_output["provider_request_id"] == "resp_live_001"
    assert response.result.structured_output["input_tokens"] == 120
    assert response.result.structured_output["output_tokens"] == 30
    assert response.result.structured_output["total_tokens"] == 150
    assert response.result.structured_output["estimated_cost_usd"] == 0.0021
    provider_evidence = next(
        descriptor
        for descriptor in response.evidence.descriptors
        if descriptor.evidence_type == "provider_resolution"
    )
    assert provider_evidence.attributes["provider_id"] == "text.openai"
    assert provider_evidence.attributes["model_id"] == "gpt-5.4"
    access_control_evidence = next(
        descriptor
        for descriptor in response.evidence.descriptors
        if descriptor.evidence_type == "access_control"
    )
    assert access_control_evidence.attributes["outcome"] == "ALLOWED"


def test_execute_task_routes_allowlisted_task_through_local_live_provider(
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
            "id": "resp_local_live_001",
            "model": "qwen3:8b",
            "output_text": "Local live explanation response.",
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        },
    )

    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == "COMPLETED"
    assert response.audit.stubbed is False
    assert response.audit.provider_mode == "local_openai_compatible"
    assert response.audit.provider_id == "text.local"
    assert response.audit.adapter_kind is not None
    assert response.audit.adapter_kind.value == "OPENAI_COMPATIBLE_LOCAL"
    assert response.audit.model_id == "qwen3:8b"
    assert response.result.message == "Local live explanation response."
    assert response.result.structured_output["provider_id"] == "text.local"
    assert response.result.structured_output["model_id"] == "qwen3:8b"


def test_execute_task_blocks_live_provider_for_caller_without_live_permission(
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

    try:
        execute_task(
            TaskExecutionRequest(
                task_id="explain.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app="lotus-advise",
                    correlation_id="corr-live-unauthorized",
                    tenant_id="tenant-us-002",
                ),
                context=TaskContextEnvelope(
                    summary="Explain advisory posture",
                    payload={"status": "PENDING_REVIEW"},
                    source_refs=[],
                ),
                expected_output_label=OutputLabel.EXPLANATION_ONLY,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "not authorized for live provider execution" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unauthorized live provider access")


def test_execute_task_reflects_promoted_prompt_selection_in_audit_and_evidence(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'task-executor-prompt-rollout.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                caller_app="lotus-platform",
                candidate_prompt_version="foundation.explain.v2",
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Promote updated explanation prompt",
            )
        )

        response = execute_task(
            _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
        )

    prompt_evidence = next(
        descriptor
        for descriptor in response.evidence.descriptors
        if descriptor.evidence_type == "prompt_selection"
    )

    assert response.audit.prompt_version == "foundation.explain.v2"
    assert response.audit.prompt_selection.prompt_version == "foundation.explain.v2"
    assert response.audit.prompt_selection.previous_active_prompt_version == "foundation.explain.v1"
    assert response.audit.prompt_selection.latest_control_event is not None
    assert (
        response.audit.prompt_selection.latest_control_event.action_type.value
        == "PROMOTE_CANDIDATE"
    )
    assert prompt_evidence.attributes["prompt_version"] == "foundation.explain.v2"
    assert prompt_evidence.attributes["previous_active_prompt_version"] == "foundation.explain.v1"
    assert prompt_evidence.attributes["latest_control_event"] is not None


def _seed_prompt_approval_gate_pass() -> None:
    for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id=fixture_id,
                caller_app="lotus-platform",
                correlation_id=f"corr-{fixture_id}",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")


def _seed_prompt_approval_gate_pass_sqlalchemy() -> None:
    for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
        get_evaluation_runtime_store().save_run(
            EvaluationRunRecord(
                run_id=f"runtime_task_executor_{fixture_id}",
                fixture_id=fixture_id,
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id=f"async_task_executor_{fixture_id}",
                latest_message="Prompt rollout approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )


def test_execute_task_failure_audit_carries_the_rejected_routing_decision(
    mocker: MockerFixture, monkeypatch: MonkeyPatch
) -> None:
    """A preflight veto (quota) must leave a routing decision on the failure
    audit record: one rejected candidate, bounded reason, no selection."""

    from app.config import settings
    from app.services.model_catalogue_store import reset_model_catalogue_store_cache

    reset_model_catalogue_store_cache()
    audit_store = mocker.Mock()
    mocker.patch("app.services.task_execution_pipeline.get_audit_store", return_value=audit_store)

    class _LiveAdapter:
        def execute(self, request: object, *, config: object | None = None) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": None,
                    "failure_category": None,
                    "timeout_ms": 4000,
                    "retry_count": 0,
                    "max_output_tokens": 512,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_reject_1",
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "estimated_cost_usd": None,
                    "rate_card_ref": None,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "provider_rollout_state", "CANARY_ENABLED")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    monkeypatch.setattr(settings, "live_text_provider_api_key", "secret")
    monkeypatch.setattr(settings, "live_text_allowed_task_ids", "explain.v1")
    monkeypatch.setattr(settings, "live_text_quota_enforced", True)
    monkeypatch.setattr(settings, "live_text_task_quota_limits", "explain.v1=1")
    monkeypatch.setattr(settings, "live_text_budget_enforced", False)
    monkeypatch.setattr(settings, "live_text_degradation_enforced", False)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")
    mocker.patch(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        return_value=_LiveAdapter(),
    )
    from app.services.provider_quota_policy import reset_provider_quota_counters

    reset_provider_quota_counters()

    from app.services.provider_gateway import ProviderGatewayUnavailableError
    from app.services.task_execution_pipeline import (
        build_failed_task_execution_response,
        validate_task_request,
    )

    first = execute_task(_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY))
    assert first.status == "COMPLETED"

    with raises(ProviderGatewayUnavailableError) as exc_info:
        execute_task(_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY))

    decision = exc_info.value.routing_decision
    assert decision.selected_provider_id is None
    assert decision.candidates[0].provider_id == "text.openai"
    assert decision.candidates[0].rejection_reason is not None
    assert decision.candidates[0].rejection_reason.value == "QUOTA_EXCEEDED"

    # The workflow-pack execution seam consumes this exception through the
    # failure builder: the rejected decision must land on the durable record
    # and in the failure evidence bundle.
    context = validate_task_request(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )
    failed = build_failed_task_execution_response(context=context, exc=exc_info.value)
    assert failed.status == "FAILED"
    assert failed.audit.routing_decision == decision
    assert any(
        descriptor.evidence_type == "routing_decision" for descriptor in failed.evidence.descriptors
    )
    # Reproducibility identity on the failure path (#151): the prompt that
    # would have run is recorded; sampling and config digests are not
    # fabricated for an execution that never reached a provider.
    assert failed.audit.prompt_content_sha256 == context.prompt.content_sha256
    assert failed.audit.sampling_parameters is None
    assert failed.audit.provider_config_sha256 is None
    reset_model_catalogue_store_cache()
