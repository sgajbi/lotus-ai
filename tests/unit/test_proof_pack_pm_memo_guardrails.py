from typing import Any, cast

from fastapi import HTTPException

from app.services.proof_pack_pm_memo_guardrails import validate_proof_pack_pm_memo_payload
from tests.support.workflow_pack_fixtures import (
    portfolio_memory_context_payload,
    proof_pack_pm_memo_payload,
)


def test_proof_pack_pm_memo_guardrails_accept_bounded_manage_ai_evidence() -> None:
    validate_proof_pack_pm_memo_payload(proof_pack_pm_memo_payload())


def test_proof_pack_pm_memo_guardrails_accept_bounded_portfolio_memory_context() -> None:
    validate_proof_pack_pm_memo_payload(
        proof_pack_pm_memo_payload(include_portfolio_memory_context=True)
    )


def test_proof_pack_pm_memo_guardrails_block_mismatched_portfolio_memory_context() -> None:
    payload = cast(
        dict[str, Any],
        proof_pack_pm_memo_payload(include_portfolio_memory_context=True),
    )
    cast(dict[str, Any], payload["portfolio_memory_context"])["portfolio_id"] = "OTHER"

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "portfolio_id must match AI evidence portfolio_id" in str(exc.detail)
    else:
        raise AssertionError("expected portfolio mismatch to block execution")


def test_proof_pack_pm_memo_guardrails_block_unbounded_portfolio_memory_context() -> None:
    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    payload["portfolio_memory_context"] = portfolio_memory_context_payload(event_ref_count=13)

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "event_refs exceeds bounded limit 12" in str(exc.detail)
    else:
        raise AssertionError("expected unbounded portfolio-memory context to block execution")


def test_proof_pack_pm_memo_guardrails_block_raw_portfolio_memory_fields() -> None:
    payload = cast(
        dict[str, Any],
        proof_pack_pm_memo_payload(include_portfolio_memory_context=True),
    )
    event_refs = cast(
        list[dict[str, Any]],
        cast(dict[str, Any], payload["portfolio_memory_context"])["event_refs"],
    )
    event_refs[0]["raw_payload"] = {"unsafe": True}

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden portfolio memory fields present: raw_payload" in str(exc.detail)
    else:
        raise AssertionError("expected raw portfolio-memory field to block execution")


def test_proof_pack_pm_memo_guardrails_block_missing_forbidden_actions() -> None:
    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    cast(dict[str, Any], payload["ai_evidence_input"])["forbidden_actions"] = ["place_orders"]

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing required forbidden-action guardrails" in str(exc.detail)
        assert "approve_rebalance" in str(exc.detail)
    else:
        raise AssertionError("expected missing forbidden actions to block execution")


def test_proof_pack_pm_memo_guardrails_block_nested_forbidden_fields() -> None:
    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    sections = cast(
        list[dict[str, Any]], cast(dict[str, Any], payload["ai_evidence_input"])["sections"]
    )
    sections[0]["bounded_facts"]["raw_payload"] = {"unsafe": True}

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden AI evidence fields present: raw_payload" in str(exc.detail)
    else:
        raise AssertionError("expected nested forbidden field to block execution")


def test_proof_pack_pm_memo_guardrails_block_forbidden_requested_outputs() -> None:
    payload = proof_pack_pm_memo_payload(requested_outputs=["pm_memo", "recommend_trade"])

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden memo outputs requested: recommend_trade" in str(exc.detail)
    else:
        raise AssertionError("expected forbidden requested output to block execution")


def test_proof_pack_pm_memo_guardrails_block_missing_required_ai_evidence() -> None:
    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    cast(dict[str, Any], payload["ai_evidence_input"]).pop("content_hash")

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Missing DpmProofPackAiEvidenceInput fields: content_hash" in str(exc.detail)
    else:
        raise AssertionError("expected missing bounded evidence hash to block execution")


def test_proof_pack_pm_memo_guardrails_block_unsupported_requested_outputs() -> None:
    payload = proof_pack_pm_memo_payload(requested_outputs=["pm_memo", "marketing_copy"])

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Unsupported memo outputs requested: marketing_copy" in str(exc.detail)
    else:
        raise AssertionError("expected unsupported requested output to block execution")


def test_proof_pack_pm_memo_guardrails_require_section_and_source_lists() -> None:
    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    ai_evidence = cast(dict[str, Any], payload["ai_evidence_input"])
    ai_evidence["sections"] = []

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "at least one bounded section" in str(exc.detail)
    else:
        raise AssertionError("expected empty sections to block execution")

    ai_evidence["sections"] = [{"section_id": "selected_alternative"}]
    ai_evidence["source_refs"] = "not-a-list"

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "source_refs must be a list" in str(exc.detail)
    else:
        raise AssertionError("expected non-list source refs to block execution")


def test_proof_pack_pm_memo_guardrails_require_object_sections_and_string_lists() -> None:
    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    payload["memo_request"] = None

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires object section `memo_request`" in str(exc.detail)
    else:
        raise AssertionError("expected missing memo request object to block execution")

    payload = cast(dict[str, Any], proof_pack_pm_memo_payload())
    cast(dict[str, Any], payload["memo_request"])["requested_outputs"] = ["pm_memo", 42]

    try:
        validate_proof_pack_pm_memo_payload(payload)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires string-list field `requested_outputs`" in str(exc.detail)
    else:
        raise AssertionError("expected non-string requested output to block execution")
