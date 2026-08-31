"""Output contracts as data (issue #156, S2).

Every registered task id and workflow-pack family carries a JSON Schema
contract; a pack without one cannot be registered; every pack family
executes through the governed stub runtime to a VALIDATED output under its
contract - including the four advisory-copilot action packs and the
proposal-memo commentary pack, which previously had no execution coverage
at all; schema violations reject in the promoted profile and mark the
output UNVALIDATED_LOCAL_ONLY in local.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from app.contracts.output_validation import OutputValidationState
from app.contracts.tasks import TaskExecutionStatus
from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.services.capability_catalog import build_capability_catalog
from app.services.output_contracts import (
    list_output_contract_keys,
    output_contract_exists,
    reset_output_contract_cache,
)
from app.services.output_validation import validate_provider_output
from app.services.workflow_pack_execution import execute_workflow_pack
from app.services.workflow_pack_registry_seed import build_seed_workflow_pack_registrations
from app.services.workflow_pack_registry import (
    get_workflow_pack_registration,
    save_workflow_pack_registration,
)
from tests.support import workflow_pack_fixtures as fixtures

_COPILOT_VARIANTS = {
    "advisory_copilot_operations_report_handoff.pack": (
        "advisory-copilot-operations-report-handoff",
        "OPERATIONS_REPORT_HANDOFF",
    ),
    "advisory_copilot_evidence_qa.pack": ("advisory-copilot-evidence-qa", "EVIDENCE_QA"),
    "advisory_copilot_meeting_preparation.pack": (
        "advisory-copilot-meeting-preparation",
        "MEETING_PREPARATION",
    ),
    "advisory_copilot_compliance_review_summary.pack": (
        "advisory-copilot-compliance-review-summary",
        "COMPLIANCE_REVIEW_SUMMARY",
    ),
    "advisory_copilot_client_follow_up_draft.pack": (
        "advisory-copilot-client-follow-up-draft",
        "CLIENT_FOLLOW_UP_DRAFT",
    ),
}

_HELPERS: dict[str, Callable[..., dict[str, object]]] = {
    "advisor_brief.pack": fixtures.advisor_brief_workflow_pack_execution_request_json,
    "workspace_rationale.pack": (fixtures.workspace_rationale_workflow_pack_execution_request_json),
    "advisory_copilot_proposal_explanation.pack": (
        fixtures.advisory_copilot_workflow_pack_execution_request_json
    ),
    "twr_inspection_support_brief.pack": (
        fixtures.twr_inspection_support_brief_workflow_pack_execution_request_json
    ),
    "dpm_pm_memo.pack": fixtures.proof_pack_pm_memo_workflow_pack_execution_request_json,
    "dpm_wave_pm_memo.pack": fixtures.wave_pm_memo_workflow_pack_execution_request_json,
    "dpm_exception_summary.pack": (
        fixtures.dpm_exception_summary_workflow_pack_execution_request_json
    ),
    "dpm_operations_handoff_summary.pack": (
        fixtures.operations_handoff_summary_workflow_pack_execution_request_json
    ),
    "outcome_review_narrative.pack": (
        fixtures.outcome_review_narrative_workflow_pack_execution_request_json
    ),
    "pm_quality_summary.pack": (fixtures.pm_quality_summary_workflow_pack_execution_request_json),
    "idea_explanation.pack": fixtures.idea_explanation_workflow_pack_execution_request_json,
    "proposal_memo_commentary.pack": (
        fixtures.proposal_memo_commentary_workflow_pack_execution_request_json
    ),
}


def _pack_request(pack_id: str) -> WorkflowPackExecutionRequest:
    correlation_id = f"corr-contract-{pack_id.split('.')[0].replace('_', '-')}"
    if pack_id in _COPILOT_VARIANTS:
        surface, family = _COPILOT_VARIANTS[pack_id]
        payload = fixtures.advisory_copilot_variant_workflow_pack_execution_request_json(
            pack_id=pack_id,
            workflow_surface=surface,
            action_family=family,
            correlation_id=correlation_id,
        )
    else:
        payload = _HELPERS[pack_id](correlation_id=correlation_id)
    return WorkflowPackExecutionRequest.model_validate(payload)


def _registered_pack_ids() -> set[str]:
    return {registration.pack_id for registration in build_seed_workflow_pack_registrations()}


def test_every_registered_task_and_pack_family_has_exactly_one_contract() -> None:
    task_ids = {task.task_id for task in build_capability_catalog().tasks}
    expected = task_ids | _registered_pack_ids()
    assert set(list_output_contract_keys()) == expected, (
        "contracts/ai-task-outputs must hold exactly one contract per registered "
        "task id and workflow-pack family - no gaps, no orphans"
    )


@pytest.mark.parametrize("pack_id", sorted(_registered_pack_ids()))
def test_every_pack_family_executes_to_a_validated_output(pack_id: str) -> None:
    response = execute_workflow_pack(_pack_request(pack_id))
    execution = response.execution
    assert execution.status == TaskExecutionStatus.COMPLETED
    assert execution.output_validation is not None
    assert execution.output_validation.validation_state is OutputValidationState.VALIDATED, (
        f"{pack_id} output failed its contract: {execution.output_validation.findings}"
    )


def test_a_pack_without_a_contract_cannot_be_registered() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    contractless = registration.model_copy(update={"pack_id": "uncontracted_family.pack"})
    with pytest.raises(ValueError, match="uncontracted_family.pack"):
        save_workflow_pack_registration(contractless)
    assert not output_contract_exists("uncontracted_family.pack")


def test_schema_violations_reject_in_promoted_and_warn_in_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import output_contracts

    directory = tmp_path / "ai-task-outputs"
    directory.mkdir()
    (directory / "strict.task.v1.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["message_kind"],
                "properties": {"message_kind": {"type": "string"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(output_contracts, "_CONTRACTS_DIR", directory)
    reset_output_contract_cache()
    try:
        nonconforming = {"message_kind": "summary", "unknown_extra": True}
        local = validate_provider_output(
            structured_output=nonconforming,
            supplied_source_refs=[],
            salvaged_json=False,
            runtime_profile="local",
            contract_key="strict.task",
        )
        assert local.validation_state is OutputValidationState.UNVALIDATED_LOCAL_ONLY
        assert any("unknown_extra" in finding for finding in local.findings)
        assert any("accepted with a warning" in finding for finding in local.findings)

        promoted = validate_provider_output(
            structured_output=nonconforming,
            supplied_source_refs=[],
            salvaged_json=False,
            runtime_profile="promoted",
            contract_key="strict.task",
        )
        assert promoted.validation_state is OutputValidationState.REJECTED
        assert promoted.failed_rule_ids == ["output_schema"]

        conforming = validate_provider_output(
            structured_output={"message_kind": "summary"},
            supplied_source_refs=[],
            salvaged_json=False,
            runtime_profile="promoted",
            contract_key="strict.task",
        )
        assert conforming.validation_state is OutputValidationState.VALIDATED
    finally:
        reset_output_contract_cache()


def test_missing_contract_fails_closed_in_promoted_and_marks_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import output_contracts

    directory = tmp_path / "ai-task-outputs"
    directory.mkdir()
    monkeypatch.setattr(output_contracts, "_CONTRACTS_DIR", directory)
    reset_output_contract_cache()
    try:
        promoted = validate_provider_output(
            structured_output={"anything": True},
            supplied_source_refs=[],
            salvaged_json=False,
            runtime_profile="promoted",
            contract_key="unwired.task",
        )
        assert promoted.validation_state is OutputValidationState.REJECTED
        assert promoted.failed_rule_ids == ["contract_missing"]

        local = validate_provider_output(
            structured_output={"anything": True},
            supplied_source_refs=[],
            salvaged_json=False,
            runtime_profile="local",
            contract_key="unwired.task",
        )
        assert local.validation_state is OutputValidationState.UNVALIDATED_LOCAL_ONLY
        assert any("accepted unvalidated" in finding for finding in local.findings)
    finally:
        reset_output_contract_cache()


def test_contract_listing_is_empty_without_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import output_contracts

    monkeypatch.setattr(output_contracts, "_CONTRACTS_DIR", tmp_path / "absent")
    assert output_contracts.list_output_contract_keys() == []


def test_schema_violation_volume_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import output_contracts

    directory = tmp_path / "ai-task-outputs"
    directory.mkdir()
    (directory / "bounded.task.v1.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": [f"field_{index}" for index in range(12)],
                "properties": {f"field_{index}": {"type": "string"} for index in range(12)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(output_contracts, "_CONTRACTS_DIR", directory)
    reset_output_contract_cache()
    try:
        violations = output_contracts.schema_violations("bounded.task", {})
        assert violations is not None
        assert len(violations) == 11
        assert violations[-1] == "further schema violations withheld from this summary"
    finally:
        reset_output_contract_cache()


def test_live_advisor_brief_output_validates_under_the_pack_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pack contract carries both shapes: the stub branch (proven above)
    and the live-transport branch normalized by the quality guardrails."""

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

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
            {"endpoint_reachable": True, "model_available": True, "blocking_reason": None},
        )(),
    )
    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_contract_live",
            "model": "qwen2.5:1.5b",
            "output_text": (
                '{"grounded_summary":"All figures stayed within tolerance.",'
                '"talking_points":[],"recommended_actions":[],"risks_and_exceptions":[]}'
            ),
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        },
    )

    with TestClient(app) as client:
        response = client.post(
            "/ai/tasks/execute",
            json={
                "task_id": "explain.v1",
                "input_mode": "STRUCTURED_CONTEXT",
                "caller": {
                    "caller_app": "lotus-gateway",
                    "correlation_id": "corr-contract-live-brief",
                    "tenant_id": "tenant-sg-001",
                },
                "context": {
                    "summary": "Generate Advisor Brief",
                    "payload": {
                        "portfolio": {"portfolio_id": "PB_X", "display_label": "PB X"},
                        "period": {"period": "YTD"},
                        "performance": {
                            "portfolio_return_pct": 1.25,
                            "benchmark_return_pct": 7.93,
                            "active_return_pct": -6.68,
                        },
                        "supportability": [{"key": "performance_context", "value": "ready"}],
                    },
                    "source_refs": ["lotus-gateway:performance-summary:YTD"],
                },
                "expected_output_label": "EXPLANATION_ONLY",
            },
            headers={"X-Caller-App": "lotus-gateway"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["output_validation"]["validation_state"] == "VALIDATED", body["output_validation"][
        "findings"
    ]
