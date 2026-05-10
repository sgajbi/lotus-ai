from typing import Any, cast

import pytest
from fastapi import HTTPException

from app.providers.operations_handoff_summary_stub import (
    build_operations_handoff_summary_stub_result,
)
from app.services.operations_handoff_summary_guardrails import (
    _single_portfolio_id,
    validate_operations_handoff_summary_payload,
)
from tests.support.workflow_pack_fixtures import (
    operations_handoff_summary_payload,
    portfolio_memory_context_payload,
)


def _assert_guardrail_rejects(payload: dict[str, object], detail: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_operations_handoff_summary_payload(payload)

    assert exc_info.value.status_code == 422
    assert detail in str(exc_info.value.detail)


def test_operations_handoff_summary_guardrails_accept_bounded_handoff_evidence() -> None:
    validate_operations_handoff_summary_payload(operations_handoff_summary_payload())


def test_operations_handoff_summary_guardrails_accept_bounded_portfolio_memory_context() -> None:
    validate_operations_handoff_summary_payload(
        operations_handoff_summary_payload(include_portfolio_memory_context=True)
    )


def test_operations_handoff_summary_guardrails_block_mixed_wave_memo_request() -> None:
    payload = operations_handoff_summary_payload()
    payload["memo_request"] = {"requested_outputs": ["wave_pm_memo"]}

    _assert_guardrail_rejects(payload, "must not include wave memo `memo_request`")


def test_operations_handoff_summary_guardrails_block_unbounded_portfolio_memory_context() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    payload["portfolio_memory_context"] = portfolio_memory_context_payload(event_ref_count=13)

    _assert_guardrail_rejects(payload, "event_refs exceeds bounded limit 12")


def test_operations_handoff_summary_guardrails_block_missing_handoff_refs() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["handoff_refs"] = []

    _assert_guardrail_rejects(payload, "requires non-empty handoff_refs")


def test_operations_handoff_summary_guardrails_block_malformed_handoff_refs() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    handoff_refs = cast(
        list[dict[str, Any]], cast(dict[str, Any], payload["wave_report_input"])["handoff_refs"]
    )
    handoff_refs[0].pop("content_hash")

    _assert_guardrail_rejects(payload, "ref_type, ref_id, source_system, and content_hash")


def test_operations_handoff_summary_guardrails_block_external_execution_claim() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["external_execution_claimed"] = True

    _assert_guardrail_rejects(payload, "cannot claim external execution authority")


def test_operations_handoff_summary_guardrails_block_forbidden_requested_outputs() -> None:
    payload = operations_handoff_summary_payload(
        requested_outputs=["operations_summary", "order_ticket"]
    )

    _assert_guardrail_rejects(
        payload, "Forbidden operations handoff outputs requested: order_ticket"
    )


def test_operations_handoff_summary_guardrails_block_unsupported_requested_outputs() -> None:
    payload = operations_handoff_summary_payload(
        requested_outputs=["operations_summary", "marketing_copy"]
    )

    _assert_guardrail_rejects(
        payload,
        "Unsupported operations handoff outputs requested: marketing_copy",
    )


def test_operations_handoff_summary_guardrails_block_raw_payload_fields() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["wave_report_input"])["items"])
    items[0]["diagnostics"]["raw_payload"] = {"unsafe": True}

    _assert_guardrail_rejects(payload, "Forbidden wave report input fields present: raw_payload")


def test_operations_handoff_summary_guardrails_block_missing_wave_fields() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"]).pop("contract_version")

    _assert_guardrail_rejects(payload, "Missing DpmWaveReportInput fields: contract_version")


def test_operations_handoff_summary_guardrails_block_missing_forbidden_actions() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["supportability"])["forbidden_actions"] = ["place_orders"]

    _assert_guardrail_rejects(payload, "Missing required forbidden-action guardrails")


def test_operations_handoff_summary_guardrails_block_invalid_redaction_policy() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["redaction_policy"] = "RAW_ALLOWED"

    _assert_guardrail_rejects(payload, "must use NO_RAW_PAYLOADS redaction policy")


def test_operations_handoff_summary_guardrails_block_missing_items() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["items"] = []

    _assert_guardrail_rejects(payload, "requires at least one bounded wave item")


def test_operations_handoff_summary_guardrails_block_items_without_ready_evidence() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["wave_report_input"])["items"])
    items[0]["state"] = "DRAFT"

    _assert_guardrail_rejects(payload, "requires staged or handoff-ready wave item evidence")


def test_operations_handoff_summary_guardrails_block_missing_source_refs() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["source_refs"] = []

    _assert_guardrail_rejects(payload, "source_refs must be a non-empty list")


def test_operations_handoff_summary_guardrails_block_non_object_sections() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    payload["handoff_summary_request"] = "not-an-object"

    _assert_guardrail_rejects(payload, "requires object section `handoff_summary_request`")


def test_operations_handoff_summary_guardrails_block_non_string_requested_outputs() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["handoff_summary_request"])["requested_outputs"] = [
        "operations_summary",
        42,
    ]

    _assert_guardrail_rejects(payload, "requires string-list field `requested_outputs`")


def test_operations_handoff_summary_guardrails_block_non_object_handoff_ref() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["wave_report_input"])["handoff_refs"] = ["not-a-ref"]

    _assert_guardrail_rejects(payload, "ref_type, ref_id, source_system, and content_hash")


def test_operations_handoff_summary_portfolio_id_helper_handles_unbounded_shapes() -> None:
    assert _single_portfolio_id("not-items") is None
    assert (
        _single_portfolio_id(
            [
                {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                {"portfolio_id": "PB_SG_GROWTH_001"},
            ]
        )
        is None
    )


def test_operations_handoff_summary_stub_handles_unbounded_optional_shapes() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    wave_report_input = cast(dict[str, Any], payload["wave_report_input"])
    wave_report_input["items"] = "not-a-list"
    cast(dict[str, Any], payload["handoff_summary_request"])["requested_outputs"] = "not-a-list"
    payload["supportability"] = "not-an-object"

    result = build_operations_handoff_summary_stub_result(context_payload=payload)

    assert result is not None
    _, structured_output = result
    assert structured_output["item_count"] == 0
    assert structured_output["blocked_item_count"] == 0
    assert structured_output["requested_outputs"] == []
    assert structured_output["forbidden_actions"] == []
    assert structured_output["unsupported_claims"] == []


def test_operations_handoff_summary_stub_ignores_malformed_unsupported_claims() -> None:
    payload = cast(dict[str, Any], operations_handoff_summary_payload())
    cast(dict[str, Any], payload["supportability"])["unsupported_claims"] = "not-a-list"

    result = build_operations_handoff_summary_stub_result(context_payload=payload)

    assert result is not None
    _, structured_output = result
    assert structured_output["unsupported_claims"] == []
