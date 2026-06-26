from typing import Any, cast

from fastapi import HTTPException

from app.services.idea_explanation_guardrails import validate_idea_explanation_payload
from tests.support.workflow_pack_fixtures import idea_explanation_payload


def test_idea_explanation_guardrails_accept_redacted_review_gated_payload() -> None:
    validate_idea_explanation_payload(idea_explanation_payload())


def test_idea_explanation_guardrails_block_raw_provider_fields() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    cast(dict[str, Any], payload["redacted_evidence_packet"])["raw_payload"] = {"unsafe": True}

    try:
        validate_idea_explanation_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "technical field `raw_payload`" in str(exc.detail)
    else:
        raise AssertionError("expected raw payload field to block Idea explanation execution")


def test_idea_explanation_guardrails_block_forbidden_requested_output() -> None:
    payload = idea_explanation_payload(
        requested_outputs=["advisor_review_summary", "client_message"]
    )

    try:
        validate_idea_explanation_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden Idea explanation outputs requested: client_message" in str(exc.detail)
    else:
        raise AssertionError("expected client-message output to block Idea explanation execution")


def test_idea_explanation_guardrails_require_review_and_forbidden_actions() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    supportability = cast(dict[str, Any], payload["supportability"])
    supportability["human_review_required"] = False

    try:
        validate_idea_explanation_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "must require human review" in str(exc.detail)
    else:
        raise AssertionError("expected missing human-review posture to block execution")

    payload = cast(dict[str, Any], idea_explanation_payload())
    cast(dict[str, Any], payload["supportability"])["forbidden_actions"] = ["place_orders"]

    try:
        validate_idea_explanation_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "missing forbidden actions" in str(exc.detail)
        assert "make_final_recommendation" in str(exc.detail)
    else:
        raise AssertionError("expected missing forbidden actions to block execution")
