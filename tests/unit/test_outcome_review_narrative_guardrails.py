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


def test_outcome_review_narrative_guardrails_block_missing_required_ai_evidence() -> None:
    payload = cast(dict[str, Any], outcome_review_narrative_payload())
    cast(dict[str, Any], payload["ai_evidence_input"]).pop("content_hash")

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing DpmOutcomeAiEvidenceInput fields: content_hash" in str(exc.detail)
    else:
        raise AssertionError("expected missing bounded evidence hash to block execution")


def test_outcome_review_narrative_guardrails_block_unsupported_requested_outputs() -> None:
    payload = outcome_review_narrative_payload(requested_outputs=["pm_summary", "marketing_copy"])

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Unsupported narrative outputs requested: marketing_copy" in str(exc.detail)
    else:
        raise AssertionError("expected unsupported requested output to block execution")


def test_outcome_review_narrative_guardrails_require_dimension_and_source_lists() -> None:
    payload = cast(dict[str, Any], outcome_review_narrative_payload())
    ai_evidence = cast(dict[str, Any], payload["ai_evidence_input"])
    ai_evidence["dimensions"] = []

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "at least one bounded dimension" in str(exc.detail)
    else:
        raise AssertionError("expected empty dimensions to block execution")

    ai_evidence["dimensions"] = [{"dimension_id": "twr"}]
    ai_evidence["source_refs"] = "not-a-list"

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "source_refs must be a list" in str(exc.detail)
    else:
        raise AssertionError("expected non-list source refs to block execution")


def test_outcome_review_narrative_guardrails_require_object_sections_and_string_lists() -> None:
    payload = cast(dict[str, Any], outcome_review_narrative_payload())
    payload["narrative_request"] = None

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires object section `narrative_request`" in str(exc.detail)
    else:
        raise AssertionError("expected missing narrative request object to block execution")

    payload = cast(dict[str, Any], outcome_review_narrative_payload())
    cast(dict[str, Any], payload["narrative_request"])["requested_outputs"] = ["pm_summary", 42]

    try:
        validate_outcome_review_narrative_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires string-list field `requested_outputs`" in str(exc.detail)
    else:
        raise AssertionError("expected non-string requested output to block execution")
