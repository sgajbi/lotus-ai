"""The capability requirement contract (issue #244, S1).

Slice 1 is vocabulary plus honesty: declared requirements are validated and
recorded as execution evidence with an explicit NOT_ENFORCED posture, and an
absent requirements object leaves every execution surface byte-identical to
before the field existed.
"""

import pytest
from pydantic import ValidationError

from app.contracts.capability_requirements import (
    REQUIREMENTS_NOT_ENFORCED,
    CapabilityRequirements,
)
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.task_executor import execute_task


def _request(requirements: CapabilityRequirements | None = None) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_id="explain.v1",
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(
            caller_app="lotus-manage",
            correlation_id="corr-requirements-001",
            tenant_id="tenant-sg-001",
        ),
        context=TaskContextEnvelope(
            summary="Explain rebalance outcome",
            payload={"status": "BLOCKED"},
            source_refs=["lotus-manage:run:reb_001"],
        ),
        requirements=requirements,
        expected_output_label=OutputLabel.EXPLANATION_ONLY,
    )


def test_an_empty_requirements_object_is_refused() -> None:
    """An empty object is a statement that means nothing; the contract makes
    'no requirements' spellable only by omission."""

    with pytest.raises(ValidationError) as exc_info:
        CapabilityRequirements()
    assert "at least one dimension" in str(exc_info.value)


def test_dimension_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        CapabilityRequirements(max_latency_ms=10)
    with pytest.raises(ValidationError):
        CapabilityRequirements(max_estimated_cost_usd=0)
    with pytest.raises(ValidationError):
        CapabilityRequirements(max_estimated_cost_usd=1_000_000)


def test_declared_dimensions_reports_only_what_was_stated() -> None:
    requirements = CapabilityRequirements(structured_output_required=True, max_latency_ms=2_000)
    assert requirements.declared_dimensions() == {
        "structured_output_required": True,
        "max_latency_ms": 2_000,
    }


def test_absent_requirements_leave_the_execution_unchanged() -> None:
    """The additive guarantee: without the field, nothing about the response
    or its evidence differs from before the contract existed."""

    response = execute_task(_request())

    assert response.status.value == "COMPLETED"
    evidence_types = [d.evidence_type for d in response.evidence.descriptors]
    assert "capability_requirements" not in evidence_types
    assert len(response.evidence.descriptors) == 8


def test_declared_requirements_are_recorded_with_an_explicit_unenforced_posture() -> None:
    """Recording a requirement without stating whether anything enforces it
    would let a consumer believe a ceiling is held when nothing holds it."""

    response = execute_task(
        _request(
            CapabilityRequirements(
                structured_output_required=True,
                max_latency_ms=2_000,
                max_estimated_cost_usd=0.25,
            )
        )
    )

    assert response.status.value == "COMPLETED"
    descriptor = next(
        d for d in response.evidence.descriptors if d.evidence_type == "capability_requirements"
    )
    assert descriptor.attributes["requirements_enforcement"] == REQUIREMENTS_NOT_ENFORCED
    assert descriptor.attributes["declared"] == {
        "structured_output_required": True,
        "max_latency_ms": 2_000,
        "max_estimated_cost_usd": 0.25,
    }
    assert "NOT_ENFORCED" in descriptor.summary
    # Requirements never grant or change routing in this slice: the serving
    # identity is exactly what it would have been without them.
    assert response.audit.provider_id == "text.stub"
