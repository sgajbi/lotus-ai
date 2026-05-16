from typing import Any, cast

from fastapi import HTTPException

from app.providers.pm_quality_summary_stub import build_pm_quality_summary_stub_result
from app.services.pm_quality_summary_guardrails import validate_pm_quality_summary_payload
from tests.support.workflow_pack_fixtures import (
    pm_quality_summary_payload,
    portfolio_memory_context_payload,
)


def test_pm_quality_summary_guardrails_accept_bounded_score_run_evidence() -> None:
    validate_pm_quality_summary_payload(pm_quality_summary_payload())


def test_pm_quality_summary_guardrails_accept_bounded_portfolio_memory_context() -> None:
    validate_pm_quality_summary_payload(
        pm_quality_summary_payload(include_portfolio_memory_context=True)
    )


def test_pm_quality_summary_guardrails_block_missing_required_score_run_field() -> None:
    payload = cast(dict[str, Any], pm_quality_summary_payload())
    cast(dict[str, Any], payload["score_run"]).pop("content_hash")

    try:
        validate_pm_quality_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing PmOperatingQualityScoreRun fields: content_hash" in str(exc.detail)
    else:
        raise AssertionError("expected missing score-run hash to block execution")


def test_pm_quality_summary_guardrails_block_forbidden_requested_outputs() -> None:
    payload = pm_quality_summary_payload(
        requested_outputs=["score_run_summary", "compensation_recommendation"]
    )

    try:
        validate_pm_quality_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden PM quality summary outputs requested" in str(exc.detail)
        assert "compensation_recommendation" in str(exc.detail)
    else:
        raise AssertionError("expected compensation output to block execution")


def test_pm_quality_summary_guardrails_block_missing_forbidden_actions() -> None:
    payload = cast(dict[str, Any], pm_quality_summary_payload())
    cast(dict[str, Any], payload["supportability"])["forbidden_actions"] = ["place_orders"]

    try:
        validate_pm_quality_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing required forbidden-action guardrails" in str(exc.detail)
        assert "rank_portfolio_managers" in str(exc.detail)
    else:
        raise AssertionError("expected missing PM-quality guardrails to block execution")


def test_pm_quality_summary_guardrails_block_raw_or_hr_fields() -> None:
    payload = cast(dict[str, Any], pm_quality_summary_payload())
    cast(dict[str, Any], payload["score_run"])["hr_rating"] = "high"

    try:
        validate_pm_quality_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden PM quality evidence fields present: hr_rating" in str(exc.detail)
    else:
        raise AssertionError("expected HR field to block execution")


def test_pm_quality_summary_guardrails_block_unbounded_portfolio_memory_context() -> None:
    payload = cast(dict[str, Any], pm_quality_summary_payload())
    payload["portfolio_memory_context"] = portfolio_memory_context_payload(event_ref_count=13)

    try:
        validate_pm_quality_summary_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "event_refs exceeds bounded limit 12" in str(exc.detail)
    else:
        raise AssertionError("expected unbounded portfolio-memory context to block execution")


def test_pm_quality_summary_stub_returns_review_gated_support_only_output() -> None:
    result = build_pm_quality_summary_stub_result(
        context_payload=pm_quality_summary_payload(include_portfolio_memory_context=True)
    )

    assert result is not None
    _, structured_output = result
    assert structured_output["workflow_pack_family"] == "pm_quality_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["score_run_content_hash"] == "sha256:pm-quality-score-run-001"
    assert structured_output["indicator_result_count"] == 1
    assert "pm_ranking" in structured_output["unsupported_claims"]
