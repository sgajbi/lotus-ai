"""Deterministic output validation (issue #156, S1).

Every AI output carries a validation verdict and the non-authoritative
marking; a fabricated evidence reference is rejected fail-closed with the
rule id, the output withheld whole, and the verdict persisted on the audit
record; salvaged JSON is rejected in promoted and marked
UNVALIDATED_LOCAL_ONLY in local; a validator fault fails closed.
"""

from collections.abc import Generator

import pytest

from app.config import settings
from app.contracts.output_validation import (
    AI_OUTPUT_AUTHORITY,
    OUTPUT_VALIDATION_RULESET_VERSION,
    OutputValidationOutcome,
    OutputValidationState,
)
from app.contracts.tasks import OutputLabel, TaskExecutionStatus
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.services.audit_store import get_audit_store
from app.services.output_validation import validate_provider_output
from app.services.task_executor import execute_task
from tests.unit.test_task_executor import _request

GROUNDED_REFS = ["lotus-manage:run:reb_001", "lotus-manage:run:reb_002"]


@pytest.fixture(autouse=True)
def _permissive_rules_contract(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """The rule-unit tests exercise one rule at a time against synthetic
    outputs, so they run under a permissive contract in an isolated
    contracts directory; the real committed contracts are exercised by the
    end-to-end and per-contract tests."""

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


def _validate(structured_output: object, **overrides: object) -> OutputValidationOutcome:
    kwargs: dict[str, object] = {
        "structured_output": structured_output,
        "supplied_source_refs": GROUNDED_REFS,
        "salvaged_json": False,
        "runtime_profile": "local",
        "contract_key": "rules.test",
    }
    kwargs.update(overrides)
    return validate_provider_output(**kwargs)  # type: ignore[arg-type]


def test_grounded_output_is_validated_with_the_authority_marking() -> None:
    outcome = _validate(
        {
            "grounded_facts": [
                {"metric_label": "Return", "source_ref": GROUNDED_REFS[0]},
                {"metric_label": "Benchmark", "source_ref": GROUNDED_REFS[1]},
            ],
            "sections": [{"evidence_refs": [GROUNDED_REFS[0]]}],
        }
    )
    assert outcome.validation_state is OutputValidationState.VALIDATED
    assert outcome.authority == AI_OUTPUT_AUTHORITY
    assert outcome.ruleset_version == OUTPUT_VALIDATION_RULESET_VERSION
    assert outcome.failed_rule_ids == []


def test_fabricated_reference_is_rejected_with_the_rule_id() -> None:
    outcome = _validate(
        {
            "narrative": "text",
            "sections": [{"evidence_refs": [GROUNDED_REFS[0], "lotus-manage:run:fabricated_999"]}],
        }
    )
    assert outcome.validation_state is OutputValidationState.REJECTED
    assert outcome.failed_rule_ids == ["evidence_grounding"]
    assert any("fabricated_999" in finding for finding in outcome.findings)


def test_reference_rules_cover_nesting_shapes_and_non_strings() -> None:
    outcome = _validate(
        {
            "deep": {"list": [{"inner": {"source_ref": "unsupplied:a"}}]},
            "evidence_ref": "unsupplied:b",
            "sections": [{"source_refs": [12345]}],
            # A structured evidence entry under a reference key is the domain
            # vocabulary (advisor-brief fact objects): its inner source_ref is
            # what gets checked.
            "points": [{"evidence_refs": [{"metric_label": "x", "source_ref": "unsupplied:c"}]}],
            "grounded_entry": {"evidence_refs": [{"source_ref": GROUNDED_REFS[0]}]},
            "duplicated": {"source_ref": "unsupplied:a"},
        }
    )
    assert outcome.validation_state is OutputValidationState.REJECTED
    joined = "\n".join(outcome.findings)
    assert "unsupplied:a" in joined and "unsupplied:b" in joined and "unsupplied:c" in joined
    assert "<non-string reference: int>" in joined
    assert GROUNDED_REFS[0] not in joined
    # Deduplicated: unsupplied:a appears once despite two citations.
    assert joined.count("unsupplied:a") == 1


def test_finding_volume_is_bounded_with_the_overflow_stated() -> None:
    outcome = _validate(
        {"sections": [{"source_ref": f"unsupplied:{index}"} for index in range(15)]}
    )
    assert outcome.validation_state is OutputValidationState.REJECTED
    assert len([f for f in outcome.findings if "unsupplied:" in f]) == 10
    assert any("5 further unsupported references withheld" in f for f in outcome.findings)


def test_empty_evidence_packet_rejects_any_citation() -> None:
    outcome = _validate({"sections": [{"source_ref": GROUNDED_REFS[0]}]}, supplied_source_refs=[])
    assert outcome.validation_state is OutputValidationState.REJECTED


def test_salvaged_json_is_local_only_and_rejected_in_promoted() -> None:
    local = _validate({"answer": "text"}, salvaged_json=True)
    assert local.validation_state is OutputValidationState.UNVALIDATED_LOCAL_ONLY
    assert local.failed_rule_ids == []
    assert any("strict_json" in finding for finding in local.findings)

    promoted = _validate({"answer": "text"}, salvaged_json=True, runtime_profile="promoted")
    assert promoted.validation_state is OutputValidationState.REJECTED
    assert promoted.failed_rule_ids == ["strict_json"]


def test_both_rule_families_report_together() -> None:
    outcome = _validate(
        {"source_ref": "unsupplied:x"}, salvaged_json=True, runtime_profile="promoted"
    )
    assert outcome.validation_state is OutputValidationState.REJECTED
    assert outcome.failed_rule_ids == ["evidence_grounding", "strict_json"]


def test_validator_fault_fails_closed_as_validation_unavailable() -> None:
    bomb: dict[str, object] = {}
    cursor = bomb
    for _ in range(40):
        nested: dict[str, object] = {}
        cursor["deeper"] = nested
        cursor = nested
    cursor["source_ref"] = "unsupplied:deep"
    outcome = _validate(bomb)
    assert outcome.validation_state is OutputValidationState.VALIDATION_UNAVAILABLE


def test_stub_execution_returns_a_validated_marked_output() -> None:
    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )
    assert response.status == TaskExecutionStatus.COMPLETED
    assert response.output_validation is not None
    assert response.output_validation.validation_state is OutputValidationState.VALIDATED
    assert response.output_validation.authority == AI_OUTPUT_AUTHORITY
    assert response.audit.output_validation == response.output_validation

    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=1)
    assert records[0].output_validation is not None
    assert records[0].output_validation.validation_state is OutputValidationState.VALIDATED


def test_fabricated_reference_is_withheld_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """The issue's core proof for a non-advisor-brief task: an output citing
    unsupplied evidence never leaves the service, and the audit record
    carries the REJECTED verdict with the rule id."""

    class _FabricatingAdapter:
        def execute(self, request: object, *, config: object) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.stub",
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": None,
                    "failure_category": None,
                    "timeout_ms": 4000,
                    "retry_count": 0,
                    "max_output_tokens": 512,
                    "model_id": "stub",
                    "model_version": None,
                    "model_catalogue_entry_id": None,
                    "model_revision_pinned": None,
                    "routing_decision": None,
                    "estimated_cost_usd": None,
                    "rate_card_ref": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "provider_request_id": "req_fab",
                    "stubbed": True,
                    "message": "A claim citing evidence that was never supplied.",
                    "structured_output": {
                        "claims": [{"source_ref": "lotus-manage:run:fabricated_777"}]
                    },
                },
            )()

    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _FabricatingAdapter(),
    )

    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == TaskExecutionStatus.REJECTED
    assert response.output_validation is not None
    assert response.output_validation.validation_state is OutputValidationState.REJECTED
    assert response.output_validation.failed_rule_ids == ["evidence_grounding"]
    # Withheld whole: neither the message nor the structured output leaves.
    assert "fabricated_777" not in response.result.message
    assert response.result.structured_output["error_code"] == "OUTPUT_VALIDATION_REJECTED"
    assert "claims" not in response.result.structured_output

    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=1)
    record = records[0]
    assert record.execution_status == TaskExecutionStatus.REJECTED
    assert record.output_validation is not None
    assert record.output_validation.validation_state is OutputValidationState.REJECTED
    assert "fabricated_777" not in record.result_preview
