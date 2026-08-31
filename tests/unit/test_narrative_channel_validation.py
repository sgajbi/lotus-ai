"""The narrative channel is validated too (issue #227).

For every family except advisor-brief the live transport returns the
model's words only as the message, so validating the structured output
alone let a fabricated figure or citation reach consumers marked
VALIDATED. These tests drive the REAL transport with a fake only at the
HTTP boundary, and pin the rule that a reference appearing ONLY in the
narrative is never self-grounding.
"""

from collections.abc import Generator

import pytest

from app.config import settings
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.contracts.output_validation import OutputValidationOutcome, OutputValidationState
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskExecutionStatus,
    TaskInputMode,
)
from app.services.audit_store import get_audit_store
from app.services.output_validation import validate_provider_output
from app.services.provider_execution_overrides import override_text_transport_post
from app.services.task_executor import execute_task

SUPPLIED_REF = "lotus-manage:run:reb_001"


@pytest.fixture(autouse=True)
def _permissive_rules_contract(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """The rule-unit cases below use synthetic outputs, so they resolve a
    permissive contract from an isolated directory that still carries the
    real contracts the end-to-end cases resolve."""

    import json
    import shutil
    from pathlib import Path

    from app.services import output_contracts

    directory = Path(str(tmp_path)) / "ai-task-outputs"
    shutil.copytree(output_contracts._CONTRACTS_DIR, directory)
    (directory / "rules.test.v1.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
    monkeypatch.setattr(output_contracts, "_CONTRACTS_DIR", directory)
    output_contracts.reset_output_contract_cache()
    yield
    output_contracts.reset_output_contract_cache()


def _validate(message: str, structured_output: dict[str, object]) -> OutputValidationOutcome:
    return validate_provider_output(
        structured_output=structured_output,
        supplied_source_refs=[SUPPLIED_REF],
        salvaged_json=False,
        runtime_profile="local",
        contract_key="rules.test",
        context_payload={"performance": {"portfolio_return_pct": 1.25}},
        message=message,
    )


def test_a_reference_only_in_the_narrative_is_never_self_grounding() -> None:
    outcome = _validate("Reviewed per lotus-manage:doc:999.", {"provider_id": "text.stub"})
    assert outcome.validation_state is OutputValidationState.REJECTED
    assert outcome.failed_rule_ids == ["evidence_grounding"]
    assert any("lotus-manage:doc:999" in finding for finding in outcome.findings)


def test_supplied_and_structured_references_ground_the_narrative() -> None:
    supplied = _validate(f"Grounded in {SUPPLIED_REF}.", {"provider_id": "text.stub"})
    assert supplied.validation_state is OutputValidationState.VALIDATED

    # The retrieval citation shape: the structured channel declares
    # source_id + document_id, the narrative renders them joined.
    composed = _validate(
        "Sources: lotus-platform-rfcs:doc-1.",
        {
            "provider_id": "retrieval.catalog",
            "citations": [{"source_id": "lotus-platform-rfcs", "document_id": "doc-1"}],
        },
    )
    assert composed.validation_state is OutputValidationState.VALIDATED


def test_narrative_numbers_must_trace_to_supplied_values() -> None:
    grounded = _validate("The portfolio returned 1.25%.", {"provider_id": "text.stub"})
    assert grounded.validation_state is OutputValidationState.VALIDATED

    fabricated = _validate("The portfolio returned 42.5%.", {"provider_id": "text.stub"})
    assert fabricated.validation_state is OutputValidationState.REJECTED
    assert fabricated.failed_rule_ids == ["numeric_grounding"]
    assert any("42.5%" in finding for finding in fabricated.findings)


def _live_summarize_settings() -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "summarize.v1"


def _summarize_request(correlation_id: str) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_id="summarize.v1",
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(
            caller_app="lotus-manage",
            correlation_id=correlation_id,
            tenant_id="tenant-sg-001",
        ),
        context=TaskContextEnvelope(
            summary="Summarize the rebalance outcome",
            payload={"status": "BLOCKED", "rule_count": 3},
            source_refs=[SUPPLIED_REF],
        ),
        expected_output_label=OutputLabel.DRAFT,
    )


def test_live_message_only_fabrication_is_rejected_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect this issue was filed for: a live non-advisor-brief family
    returns its narrative solely as the message, and a fabricated figure
    plus a fabricated citation there must not reach a consumer VALIDATED."""

    _live_summarize_settings()
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {"endpoint_reachable": True, "model_available": True, "blocking_reason": None},
        )(),
    )

    fabricated = "The portfolio returned 42.5% (per lotus-manage:doc:999)."
    with override_text_transport_post(
        lambda **_: {
            "id": "resp_narrative_fabrication",
            "model": "qwen3:8b",
            "output_text": fabricated,
            "usage": {"input_tokens": 10, "output_tokens": 6, "total_tokens": 16},
        }
    ):
        response = execute_task(_summarize_request("corr-227-fabrication"))

    assert response.status == TaskExecutionStatus.REJECTED
    assert response.output_validation is not None
    assert response.output_validation.validation_state is OutputValidationState.REJECTED
    assert response.output_validation.failed_rule_ids == [
        "evidence_grounding",
        "numeric_grounding",
    ]
    # Withheld whole: neither the figure nor the citation leaves the service.
    assert "42.5%" not in response.result.message
    assert "lotus-manage:doc:999" not in response.result.message

    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=5)
    record = next(r for r in records if r.correlation_id == "corr-227-fabrication")
    assert record.execution_status == TaskExecutionStatus.REJECTED
    assert "42.5%" not in record.result_preview


def test_live_grounded_narrative_is_validated_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live_summarize_settings()
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {"endpoint_reachable": True, "model_available": True, "blocking_reason": None},
        )(),
    )

    with override_text_transport_post(
        lambda **_: {
            "id": "resp_narrative_grounded",
            "model": "qwen3:8b",
            "output_text": f"The rebalance is blocked; see {SUPPLIED_REF}.",
            "usage": {"input_tokens": 10, "output_tokens": 6, "total_tokens": 16},
        }
    ):
        response = execute_task(_summarize_request("corr-227-grounded"))

    assert response.status == TaskExecutionStatus.COMPLETED
    assert response.output_validation is not None
    assert response.output_validation.validation_state is OutputValidationState.VALIDATED


def test_knowledge_answer_citations_are_not_false_positives() -> None:
    """The deterministic retrieval answer renders its citations as
    `source_id:document_id` in the narrative while the structured channel
    declares the parts - it must stay VALIDATED."""

    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-227-knowledge",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Answer from approved sources",
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

    assert response.status == TaskExecutionStatus.COMPLETED
    assert response.output_validation is not None
    assert response.output_validation.validation_state is OutputValidationState.VALIDATED, (
        response.output_validation.findings
    )
