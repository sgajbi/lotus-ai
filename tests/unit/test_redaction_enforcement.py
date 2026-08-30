"""End-to-end redaction enforcement (issue #150, S2 evaluation condition)."""

from fastapi import HTTPException
from pytest import MonkeyPatch, raises

from app.config import settings
from app.contracts.providers import ProviderAdapterKind, ProviderExecutionResponse
from app.contracts.tasks import OutputLabel, TaskExecutionResponse
from app.contracts.audit_access import AuditReadScope
from app.services.audit_store import get_audit_store
from app.services.task_executor import execute_task
from tests.unit.test_task_executor import _request

VALID_PAN = "4111111111111111"
EMAIL = "client.owner@lotus.test"


def _leaky_provider_response() -> ProviderExecutionResponse:
    return ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="disabled",
        adapter_kind=ProviderAdapterKind.STUB,
        stubbed=True,
        message=f"Card {VALID_PAN} for {EMAIL} was reviewed.",
        structured_output={"note": f"Contact {EMAIL}.", "phase": "foundation"},
    )


def _execute_leaky_task(monkeypatch: MonkeyPatch) -> TaskExecutionResponse:
    monkeypatch.setattr(
        "app.services.task_execution_pipeline.execute_text_generation",
        lambda request: _leaky_provider_response(),
    )
    return execute_task(_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY))


def test_enforce_mode_redacts_response_and_stored_audit_record(
    monkeypatch: MonkeyPatch,
) -> None:
    response = _execute_leaky_task(monkeypatch)

    # Neither the response nor the persisted audit record contains the
    # identifiers (issue #150 evaluation condition).
    assert VALID_PAN not in response.result.message
    assert EMAIL not in response.result.message
    assert EMAIL not in str(response.result.structured_output)
    assert "[REDACTED:card_pan]" in response.result.message
    findings = {item.finding_type: item.count for item in response.audit.safety.redactions}
    assert findings == {"card_pan": 1, "email": 2}
    assert response.audit.safety.runtime_redaction_active is True

    stored = get_audit_store().list(
        scope=AuditReadScope.restricted(frozenset({"tenant-sg-001"})), limit=1
    )[0]
    assert VALID_PAN not in stored.result_preview
    assert EMAIL not in stored.result_preview
    assert EMAIL not in str(stored.structured_output)
    stored_findings = {item.finding_type: item.count for item in stored.safety_outcome.redactions}
    assert stored_findings == {"card_pan": 1, "email": 2}


def test_observe_mode_counts_findings_without_modifying_content(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.redaction_mode = "observe"

    response = _execute_leaky_task(monkeypatch)

    assert VALID_PAN in response.result.message
    assert EMAIL in response.result.message
    findings = {item.finding_type: item.count for item in response.audit.safety.redactions}
    assert findings == {"card_pan": 1, "email": 2}
    assert response.audit.safety.runtime_redaction_active is False
    engine_result = next(
        item
        for item in response.audit.safety.control_results
        if item.control_id == "runtime_redaction_engine"
    )
    assert engine_result.execution_state.value == "OBSERVED"


def test_engine_failure_fails_closed_in_enforce_mode(monkeypatch: MonkeyPatch) -> None:
    def _broken(*args: object, **kwargs: object) -> object:
        raise ValueError("detector exploded")

    monkeypatch.setattr("app.services.safety_enforcement.redact_text", _broken)

    with raises(HTTPException) as exc_info:
        _execute_leaky_task(monkeypatch)

    assert exc_info.value.status_code == 503
    assert "SAFETY_REDACTION_UNAVAILABLE" in str(exc_info.value.detail)


def test_engine_failure_passes_through_in_observe_mode(monkeypatch: MonkeyPatch) -> None:
    settings.redaction_mode = "observe"

    def _broken(*args: object, **kwargs: object) -> object:
        raise ValueError("detector exploded")

    monkeypatch.setattr("app.services.safety_enforcement.redact_text", _broken)

    response = _execute_leaky_task(monkeypatch)

    assert VALID_PAN in response.result.message
    assert response.audit.safety.redactions == []
