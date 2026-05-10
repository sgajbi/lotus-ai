from typing import Any, cast

from fastapi import HTTPException

from app.services.operations_handoff_summary_guardrails import (
    validate_operations_handoff_summary_payload,
)
from tests.support.workflow_pack_fixtures import (
    operations_handoff_summary_payload,
    portfolio_memory_context_payload,
)


def test_operations_handoff_summary_guardrails_accept_bounded_handoff_evidence() -> None:
    validate_operations_handoff_summary_payload(operations_handoff_summary_payload())


def test_operations_handoff_summary_guardrails_accept_bounded_portfolio_memory_context() -> None:
    validate_operations_handoff_summary_payload(
        operations_handoff_summary_payload(include_portfolio_memory_context=True)
    )


def test_operations_handoff_summary_guardrails_block_mixed_wave_memo_request() -> None:
    payload = operations_handoff_summary_payload()
    payload["memo_request"] = {"requested_outputs": ["wave_pm_memo"]}

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "must not include wave memo `memo_request`" in str(exc.detail)
    else:
        raise AssertionError("expected mixed memo and handoff requests to block execution")


def test_operations_handoff_summary_guardrails_block_unbounded_portfolio_memory_context() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    payload["portfolio_memory_context"] = portfolio_memory_context_payload(event_ref_count=13)

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "event_refs exceeds bounded limit 12" in str(exc.detail)
    else:
        raise AssertionError("expected unbounded portfolio-memory context to block execution")


def test_operations_handoff_summary_guardrails_block_missing_handoff_refs() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["handoff_refs"] = []

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires non-empty handoff_refs" in str(exc.detail)
    else:
        raise AssertionError("expected missing handoff refs to block execution")


def test_operations_handoff_summary_guardrails_block_malformed_handoff_refs() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    handoff_refs = cast(
        list[dict[str, Any]], cast(dict[str, Any], payload["wave_report_input"])["handoff_refs"]
    )
    handoff_refs[0].pop("content_hash")

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "ref_type, ref_id, source_system, and content_hash" in str(exc.detail)
    else:
        raise AssertionError("expected malformed handoff refs to block execution")


def test_operations_handoff_summary_guardrails_block_external_execution_claim() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["external_execution_claimed"] = True

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "cannot claim external execution authority" in str(exc.detail)
    else:
        raise AssertionError("expected external execution claim to block execution")


def test_operations_handoff_summary_guardrails_block_forbidden_requested_outputs() -> None:
    payload = operations_handoff_summary_payload(
        requested_outputs=["operations_summary", "order_ticket"]
    )

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden operations handoff outputs requested: order_ticket" in str(exc.detail)
    else:
        raise AssertionError("expected forbidden handoff output to block execution")


def test_operations_handoff_summary_guardrails_block_unsupported_requested_outputs() -> None:
    payload = operations_handoff_summary_payload(
        requested_outputs=["operations_summary", "marketing_copy"]
    )

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Unsupported operations handoff outputs requested: marketing_copy" in str(exc.detail)
    else:
        raise AssertionError("expected unsupported handoff output to block execution")


def test_operations_handoff_summary_guardrails_block_raw_payload_fields() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["wave_report_input"])["items"])
    items[0]["diagnostics"]["raw_payload"] = {"unsafe": True}

    try:
        validate_operations_handoff_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden wave report input fields present: raw_payload" in str(exc.detail)
    else:
        raise AssertionError("expected forbidden raw payload field to block execution")
