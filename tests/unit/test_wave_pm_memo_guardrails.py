from typing import Any, cast

from fastapi import HTTPException

from app.services.wave_pm_memo_guardrails import validate_wave_pm_memo_payload
from tests.support.workflow_pack_fixtures import (
    portfolio_memory_context_payload,
    wave_pm_memo_payload,
)


def test_wave_pm_memo_guardrails_accept_bounded_manage_wave_report_input() -> None:
    validate_wave_pm_memo_payload(wave_pm_memo_payload())


def test_wave_pm_memo_guardrails_accept_bounded_portfolio_memory_context() -> None:
    validate_wave_pm_memo_payload(wave_pm_memo_payload(include_portfolio_memory_context=True))


def test_wave_pm_memo_guardrails_block_unbounded_portfolio_memory_context() -> None:
    payload = cast(dict[str, Any], wave_pm_memo_payload())
    payload["portfolio_memory_context"] = portfolio_memory_context_payload(event_ref_count=13)

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "event_refs exceeds bounded limit 12" in str(exc.detail)
    else:
        raise AssertionError("expected unbounded portfolio-memory context to block execution")


def test_wave_pm_memo_guardrails_block_missing_required_wave_report_input() -> None:
    payload = cast(dict[str, Any], wave_pm_memo_payload())
    cast(dict[str, Any], payload["wave_report_input"]).pop("content_hash")

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing DpmWaveReportInput fields: content_hash" in str(exc.detail)
    else:
        raise AssertionError("expected missing bounded wave report hash to block execution")


def test_wave_pm_memo_guardrails_block_nested_forbidden_fields() -> None:
    payload = cast(dict[str, Any], wave_pm_memo_payload())
    items = cast(list[dict[str, Any]], cast(dict[str, Any], payload["wave_report_input"])["items"])
    items[0]["diagnostics"]["raw_payload"] = {"unsafe": True}

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden wave report input fields present: raw_payload" in str(exc.detail)
    else:
        raise AssertionError("expected nested forbidden field to block execution")


def test_wave_pm_memo_guardrails_block_missing_forbidden_actions() -> None:
    payload = cast(dict[str, Any], wave_pm_memo_payload())
    cast(dict[str, Any], payload["supportability"])["forbidden_actions"] = ["place_orders"]

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing required forbidden-action guardrails" in str(exc.detail)
        assert "approve_rebalance" in str(exc.detail)
    else:
        raise AssertionError("expected missing forbidden actions to block execution")


def test_wave_pm_memo_guardrails_block_forbidden_requested_outputs() -> None:
    payload = wave_pm_memo_payload(requested_outputs=["wave_pm_memo", "recommend_trade"])

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden wave memo outputs requested: recommend_trade" in str(exc.detail)
    else:
        raise AssertionError("expected forbidden requested output to block execution")


def test_wave_pm_memo_guardrails_block_unsupported_requested_outputs() -> None:
    payload = wave_pm_memo_payload(requested_outputs=["wave_pm_memo", "marketing_copy"])

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Unsupported wave memo outputs requested: marketing_copy" in str(exc.detail)
    else:
        raise AssertionError("expected unsupported requested output to block execution")


def test_wave_pm_memo_guardrails_require_items_and_source_refs() -> None:
    payload = cast(dict[str, Any], wave_pm_memo_payload())
    wave_report_input = cast(dict[str, Any], payload["wave_report_input"])
    wave_report_input["items"] = []

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "at least one bounded wave item" in str(exc.detail)
    else:
        raise AssertionError("expected empty wave items to block execution")

    wave_report_input["items"] = [{"portfolio_id": "PB_SG_GLOBAL_BAL_001"}]
    wave_report_input["source_refs"] = []

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "source_refs must be a non-empty list" in str(exc.detail)
    else:
        raise AssertionError("expected empty source refs to block execution")


def test_wave_pm_memo_guardrails_block_execution_claims() -> None:
    payload = cast(dict[str, Any], wave_pm_memo_payload())
    cast(dict[str, Any], payload["wave_report_input"])["external_execution_claimed"] = True

    try:
        validate_wave_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "cannot claim external execution authority" in str(exc.detail)
    else:
        raise AssertionError("expected execution claim to block execution")
