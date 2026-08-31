"""The #156 evaluation condition, end to end.

A dpm_pm_memo.pack run whose provider output cites a source ref not in the
evidence packet and a percentage not present in the inputs is REJECTED
with both rule ids, and nothing is persisted as VALIDATED; the same inputs
with a grounded output are VALIDATED. The eval runtime executes through
the same pipeline, so eval verdicts and production verdicts agree by
construction - proven here by reading the validation verdict off an
eval-path execution.
"""

import pytest

from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.contracts.output_validation import OutputValidationState
from app.contracts.tasks import TaskExecutionStatus
from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.services.audit_store import get_audit_store
from app.services.workflow_pack_execution import execute_workflow_pack
from tests.support.workflow_pack_fixtures import (
    proof_pack_pm_memo_workflow_pack_execution_request_json,
)

CORRELATION_ID = "corr-156-evaluation-condition"


def _dpm_pm_memo_request() -> WorkflowPackExecutionRequest:
    return WorkflowPackExecutionRequest.model_validate(
        proof_pack_pm_memo_workflow_pack_execution_request_json(correlation_id=CORRELATION_ID)
    )


class _FabricatingAdapter:
    """A provider whose memo cites evidence never supplied and a percentage
    absent from the inputs - the exact failure the ecosystem directive
    forbids."""

    def execute(self, request: object, *, config: object) -> object:
        return type(
            "Response",
            (),
            {
                "provider_id": "text.stub",
                "provider_mode": "disabled",
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
                "provider_request_id": "req_eval_condition",
                "stubbed": True,
                "message": "The wave returned 42.5% and is fully supported.",
                "structured_output": {
                    "pm_memo": "The selected alternative returned 42.5% against model.",
                    "sections": [
                        {"source_ref": "lotus-manage:proof-pack:fabricated_never_supplied"}
                    ],
                },
            },
        )()


def test_fabricated_memo_is_rejected_with_both_rule_ids_and_never_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _FabricatingAdapter(),
    )

    response = execute_workflow_pack(_dpm_pm_memo_request())
    execution = response.execution

    assert execution.status == TaskExecutionStatus.REJECTED
    assert execution.output_validation is not None
    assert execution.output_validation.validation_state is OutputValidationState.REJECTED
    assert execution.output_validation.failed_rule_ids == [
        "evidence_grounding",
        "numeric_grounding",
    ]
    joined = "\n".join(execution.output_validation.findings)
    assert "fabricated_never_supplied" in joined
    assert "42.5%" in joined

    # Withheld whole: the fabricated content reaches neither the caller...
    assert "42.5%" not in execution.result.message
    assert "pm_memo" not in execution.result.structured_output

    # ...nor any persisted record as VALIDATED.
    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=5)
    record = next(r for r in records if r.correlation_id == CORRELATION_ID)
    assert record.execution_status == TaskExecutionStatus.REJECTED
    assert record.output_validation is not None
    assert record.output_validation.validation_state is OutputValidationState.REJECTED
    assert "42.5%" not in record.result_preview


def test_the_same_inputs_with_a_grounded_output_are_validated() -> None:
    response = execute_workflow_pack(_dpm_pm_memo_request())
    execution = response.execution

    assert execution.status == TaskExecutionStatus.COMPLETED
    assert execution.output_validation is not None
    assert execution.output_validation.validation_state is OutputValidationState.VALIDATED

    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=5)
    record = next(r for r in records if r.correlation_id == CORRELATION_ID)
    assert record.output_validation is not None
    assert record.output_validation.validation_state is OutputValidationState.VALIDATED


def test_eval_path_executions_carry_the_same_validation_verdict() -> None:
    """The eval runtime calls execute_task - the production pipeline - so its
    verdicts are production verdicts. Read one off an eval-path execution."""

    from app.contracts.tasks import (
        CallerMetadata,
        TaskContextEnvelope,
        TaskExecutionRequest,
        TaskInputMode,
    )
    from app.services.task_executor import execute_task

    response = execute_task(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="eval-verdict-agreement",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Explain rebalance outcome",
                payload={"status": "BLOCKED", "rule_count": 3},
                source_refs=["lotus-manage:run:reb_001"],
            ),
        )
    )
    assert response.output_validation is not None
    assert response.output_validation.validation_state is OutputValidationState.VALIDATED
    assert response.output_validation.ruleset_version == "output-validation.v3"
