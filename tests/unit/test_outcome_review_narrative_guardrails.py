from typing import Any, cast

from fastapi import HTTPException

from app.services.outcome_review_narrative_guardrails import (
    validate_outcome_review_narrative_payload,
)
from tests.support.workflow_pack_fixtures import outcome_review_narrative_payload


def test_outcome_review_narrative_guardrails_accept_bounded_manage_ai_evidence() -> None:
    validate_outcome_review_narrative_payload(outcome_review_narrative_payload())


def test_outcome_review_narrative_guardrails_block_missing_forbidden_actions() -> None:
    payload = cast(dict[str, Any], outcome_review_narrative_payload())
    cast(dict[str, Any], payload["ai_evidence_input"])["forbidden_actions"] = ["place_orders"]

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing required forbidden-action guardrails" in str(exc.detail)
        assert "score_portfolio_manager" in str(exc.detail)
    else:
        raise AssertionError("expected missing forbidden actions to block execution")


def test_outcome_review_narrative_guardrails_block_nested_forbidden_fields() -> None:
    payload = cast(dict[str, Any], outcome_review_narrative_payload())
    dimensions = cast(
        list[dict[str, Any]], cast(dict[str, Any], payload["ai_evidence_input"])["dimensions"]
    )
    dimensions[0]["raw_response"] = {"unsafe": True}

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden AI evidence fields present: raw_response" in str(exc.detail)
    else:
        raise AssertionError("expected nested forbidden field to block execution")


def test_outcome_review_narrative_guardrails_block_forbidden_requested_outputs() -> None:
    payload = outcome_review_narrative_payload(requested_outputs=["pm_summary", "client_message"])

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden narrative outputs requested: client_message" in str(exc.detail)
    else:
        raise AssertionError("expected forbidden requested output to block execution")
