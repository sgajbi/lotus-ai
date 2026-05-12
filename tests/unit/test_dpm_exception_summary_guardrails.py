from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException

from app.providers.dpm_exception_summary_stub import build_dpm_exception_summary_stub_result
from app.services.dpm_exception_summary_guardrails import (
    validate_dpm_exception_summary_payload,
)
from tests.support.workflow_pack_fixtures import dpm_exception_summary_payload


def _assert_guardrail_blocks(payload: dict[str, object], expected_detail: str) -> None:
    try:
        validate_dpm_exception_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "DPM_EXCEPTION_SUMMARY_GUARDRAIL_BLOCKED" in str(exc.detail)
        assert expected_detail in str(exc.detail)
    else:
        raise AssertionError("expected exception summary guardrail block")


def test_dpm_exception_summary_guardrails_accept_bounded_exception_evidence() -> None:
    validate_dpm_exception_summary_payload(dpm_exception_summary_payload())


def test_dpm_exception_summary_guardrails_accept_bounded_portfolio_memory_context() -> None:
    validate_dpm_exception_summary_payload(
        dpm_exception_summary_payload(include_portfolio_memory_context=True)
    )


def test_dpm_exception_summary_guardrails_block_missing_required_input_section() -> None:
    payload = dpm_exception_summary_payload()
    payload.pop("exception_summary_input")

    _assert_guardrail_blocks(payload, "requires object section `exception_summary_input`")


def test_dpm_exception_summary_guardrails_block_unbounded_exception_rows() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["exceptions"][0].pop("source_refs")

    _assert_guardrail_blocks(payload, "Each exception must carry")


def test_dpm_exception_summary_guardrails_block_empty_exceptions() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["exceptions"] = []

    _assert_guardrail_blocks(payload, "requires at least one bounded monitoring exception")


def test_dpm_exception_summary_guardrails_block_count_mismatch() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["exception_count"] = 99

    _assert_guardrail_blocks(payload, "exception_count must equal")


def test_dpm_exception_summary_guardrails_block_unbounded_top_level_source_refs() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["source_refs"] = [{"source_system": "lotus-manage"}]

    _assert_guardrail_blocks(payload, "source_refs must be bounded and source-linked")


def test_dpm_exception_summary_guardrails_block_empty_top_level_source_refs() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["source_refs"] = []

    _assert_guardrail_blocks(payload, "source_refs must be a non-empty list")


def test_dpm_exception_summary_guardrails_block_unbounded_evidence_ref() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["evidence_ref"] = {"source_system": "lotus-manage"}

    _assert_guardrail_blocks(payload, "evidence_ref must be bounded and source-linked")


def test_dpm_exception_summary_guardrails_block_portfolio_mismatch() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["exceptions"][0]["portfolio_id"] = "OTHER_PORTFOLIO"

    _assert_guardrail_blocks(payload, "portfolio_id must match all supplied exceptions")


def test_dpm_exception_summary_guardrails_block_forbidden_requested_outputs() -> None:
    payload = dpm_exception_summary_payload(
        requested_outputs=["exception_summary", "client_message"]
    )

    _assert_guardrail_blocks(payload, "Forbidden exception summary outputs requested")


def test_dpm_exception_summary_guardrails_block_unsupported_requested_outputs() -> None:
    payload = dpm_exception_summary_payload(
        requested_outputs=["exception_summary", "marketing_copy"]
    )

    _assert_guardrail_blocks(payload, "Unsupported exception summary outputs requested")


def test_dpm_exception_summary_guardrails_require_forbidden_actions() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["supportability"]["forbidden_actions"].remove("score_portfolio_manager")

    _assert_guardrail_blocks(payload, "Missing required forbidden-action guardrails")


def test_dpm_exception_summary_guardrails_block_raw_payload_policy() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["redaction_policy"] = "RAW_PAYLOADS_ALLOWED"

    _assert_guardrail_blocks(payload, "NO_RAW_PAYLOADS")


def test_dpm_exception_summary_guardrails_block_nested_forbidden_fields() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_input"]["diagnostics"] = [{"raw_payload": {"unsafe": True}}]

    _assert_guardrail_blocks(payload, "Forbidden exception summary input fields present")


def test_dpm_exception_summary_guardrails_require_string_requested_outputs() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["exception_summary_request"]["requested_outputs"] = ["exception_summary", 7]

    _assert_guardrail_blocks(payload, "requires string-list field `requested_outputs`")


def test_dpm_exception_summary_guardrails_require_string_forbidden_actions() -> None:
    payload = cast(dict[str, Any], dpm_exception_summary_payload())
    payload["supportability"]["forbidden_actions"] = ["place_orders", 7]

    _assert_guardrail_blocks(payload, "requires string-list field `forbidden_actions`")


def test_dpm_exception_summary_guardrails_block_mismatched_portfolio_memory_context() -> None:
    payload = cast(
        dict[str, Any],
        dpm_exception_summary_payload(include_portfolio_memory_context=True),
    )
    payload["portfolio_memory_context"]["portfolio_id"] = "OTHER_PORTFOLIO"

    _assert_guardrail_blocks(payload, "portfolio_id must match")


def test_dpm_exception_summary_stub_returns_review_gated_support_only_output() -> None:
    result = build_dpm_exception_summary_stub_result(
        context_payload=dpm_exception_summary_payload(include_portfolio_memory_context=True)
    )

    assert result is not None
    message, structured_output = result
    assert "review-gated DPM exception summary" in message
    assert structured_output["workflow_pack_family"] == "dpm_exception_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["exception_count"] == 2
    assert structured_output["open_exception_count"] == 2
    assert structured_output["high_exception_count"] == 1
    assert structured_output["portfolio_memory_event_count"] == 2
    unsupported_claims = cast(list[str], structured_output["unsupported_claims"])
    assert "portfolio_manager_scoring" in unsupported_claims


def test_dpm_exception_summary_stub_handles_malformed_optional_sections() -> None:
    assert build_dpm_exception_summary_stub_result(context_payload={}) is None

    result = build_dpm_exception_summary_stub_result(
        context_payload={
            "exception_summary_input": {
                "portfolio_id": 101,
                "mandate_id": None,
                "content_hash": None,
                "exceptions": "not-a-list",
            },
            "exception_summary_request": {"requested_outputs": "exception_summary"},
            "supportability": {"unsupported_claims": "not-a-list"},
        }
    )

    assert result is not None
    _message, structured_output = result
    assert structured_output["portfolio_id"] == ""
    assert structured_output["mandate_id"] == ""
    assert structured_output["exception_summary_content_hash"] == ""
    assert structured_output["requested_outputs"] == []
    assert structured_output["exception_count"] == 0
    assert structured_output["open_exception_count"] == 0
    assert structured_output["critical_exception_count"] == 0
    assert structured_output["high_exception_count"] == 0
    assert structured_output["unsupported_claims"] == []
