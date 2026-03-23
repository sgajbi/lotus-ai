from app.config import settings
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.tasks import OutputLabel
from app.services.safety_enforcement import (
    apply_safety_enforcement,
    resolve_safety_execution_outcome,
    resolve_safety_policy_for_output,
)


def test_safety_enforcement_maps_output_labels_to_typed_documented_only_outcomes() -> None:
    explanation_policy = resolve_safety_policy_for_output(OutputLabel.EXPLANATION_ONLY)
    draft_policy = resolve_safety_policy_for_output(OutputLabel.DRAFT)

    assert explanation_policy.redaction_posture == "MINIMIZATION_REQUIRED"
    assert draft_policy.redaction_posture == "DOCUMENTED_ONLY"
    assert explanation_policy.runtime_redaction_available is False
    assert draft_policy.runtime_redaction_available is False

    explanation_outcome = resolve_safety_execution_outcome(explanation_policy)
    draft_outcome = resolve_safety_execution_outcome(draft_policy)

    assert explanation_outcome.disposition == "DOCUMENTED_ONLY"
    assert draft_outcome.disposition == "DOCUMENTED_ONLY"
    assert explanation_outcome.runtime_redaction_active is False
    assert draft_outcome.runtime_redaction_active is False
    assert explanation_outcome.control_results[-1].control_id == "runtime_redaction_engine"
    assert draft_outcome.control_results[-1].execution_state == "DOCUMENTED_ONLY"


def test_safety_enforcement_redacts_bounded_output_when_runtime_enforced() -> None:
    settings.safety_mode = "runtime_enforced"
    policy = resolve_safety_policy_for_output(OutputLabel.EXPLANATION_ONLY)

    provider_execution = ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="stub",
        stubbed=True,
        message="Stub execution completed for foundation-phase task explain.v1 requested by lotus-manage.",
        structured_output={
            "context_summary": "Explain rebalance outcome",
            "context_keys": ["status"],
            "source_refs": ["lotus-manage:run:reb_001"],
        },
    )

    safe_execution, outcome = apply_safety_enforcement(
        policy=policy,
        provider_execution=provider_execution,
    )

    assert outcome.disposition == "ENFORCED_REDACTED"
    assert outcome.runtime_redaction_active is True
    assert (
        safe_execution.message == "Stub execution completed for foundation-phase task explain.v1."
    )
    assert "context_summary" not in safe_execution.structured_output
    assert "source_refs" not in safe_execution.structured_output
    assert safe_execution.structured_output["context_keys"] == ["status"]

    settings.safety_mode = "documented_only"


def test_safety_enforcement_blocks_unsupported_raw_context_echo() -> None:
    settings.safety_mode = "runtime_enforced"
    policy = resolve_safety_policy_for_output(OutputLabel.EXPLANATION_ONLY)

    provider_execution = ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="stub",
        stubbed=True,
        message="Unsafe payload.",
        structured_output={"context_payload": {"account_number": "12345"}},
    )

    safe_execution, outcome = apply_safety_enforcement(
        policy=policy,
        provider_execution=provider_execution,
    )

    assert outcome.disposition == "BLOCKED"
    assert outcome.runtime_redaction_active is True
    assert "unsupported raw context echo fields" in outcome.decision_summary
    assert safe_execution.message == "Task output blocked by deterministic runtime safety enforcement."
    assert safe_execution.structured_output["safety_blocked"] is True

    settings.safety_mode = "documented_only"


def test_safety_enforcement_degrades_to_generic_message_when_preview_cannot_be_preserved() -> None:
    settings.safety_mode = "runtime_enforced"
    policy = resolve_safety_policy_for_output(OutputLabel.EXPLANATION_ONLY)

    provider_execution = ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="stub",
        stubbed=True,
        message=" requested by lotus-manage",
        structured_output={
            "context_summary": "Explain rebalance outcome",
        },
    )

    safe_execution, outcome = apply_safety_enforcement(
        policy=policy,
        provider_execution=provider_execution,
    )

    assert outcome.disposition == "DEGRADED"
    assert (
        safe_execution.message
        == "Safety-minimized output generated for bounded Lotus task execution."
    )
    assert safe_execution.structured_output["safety_fallback"] == "GENERIC_MINIMIZED_MESSAGE"

    settings.safety_mode = "documented_only"
