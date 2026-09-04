from typing import Any, cast

from fastapi import HTTPException
import pytest

from app.providers.idea_explanation_stub import build_idea_explanation_stub_result
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


@pytest.mark.parametrize(
    ("mutator", "expected_detail"),
    [
        (
            lambda payload: cast(dict[str, Any], payload["redacted_evidence_packet"]).pop(
                "candidate_id"
            ),
            "redacted evidence missing: candidate_id",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["redacted_evidence_packet"]).__setitem__(
                "evidence_content_hash",
                "md5:not-supported",
            ),
            "must carry a sha256 content hash",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["redacted_evidence_packet"]).__setitem__(
                "source_refs",
                [],
            ),
            "redacted evidence missing: source_refs",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["redacted_evidence_packet"]).__setitem__(
                "source_refs",
                ["not-structured"],
            ),
            "source refs must be structured objects",
        ),
        (
            lambda payload: cast(
                list[dict[str, Any]],
                cast(dict[str, Any], payload["redacted_evidence_packet"])["source_refs"],
            )[0].pop("source_system"),
            "source refs must include source_system",
        ),
        (
            lambda payload: cast(
                list[dict[str, Any]],
                cast(dict[str, Any], payload["redacted_evidence_packet"])["source_refs"],
            )[0].pop("product_id"),
            "source refs must include product_id",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["explanation_request"]).pop("request_id"),
            "request must include request_id",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["explanation_request"]).__setitem__(
                "workflow_pack_id",
                "wrong.pack",
            ),
            "must identify the Idea workflow pack",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["explanation_request"]).__setitem__(
                "requested_outputs",
                ["advisor_review_summary", "unsupported_output"],
            ),
            "Unsupported Idea explanation outputs requested: unsupported_output",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["supportability"]).__setitem__(
                "client_ready_publication",
                "ALLOWED",
            ),
            "must block client-ready publication",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["supportability"]).__setitem__(
                "unsupported_claims",
                ["client_ready_publication"],
            ),
            "missing unsupported claims",
        ),
        (
            lambda payload: payload.__setitem__("redacted_evidence_packet", []),
            "payload requires `redacted_evidence_packet`",
        ),
        (
            lambda payload: cast(dict[str, Any], payload["explanation_request"]).__setitem__(
                "requested_outputs",
                "advisor_review_summary",
            ),
            "must include bounded requested_outputs",
        ),
    ],
)
def test_idea_explanation_guardrails_reject_invalid_source_safe_contracts(
    mutator: Any,
    expected_detail: str,
) -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    mutator(payload)

    with pytest.raises(HTTPException) as exc_info:
        validate_idea_explanation_payload(payload)

    assert exc_info.value.status_code == 422
    assert expected_detail in str(exc_info.value.detail)


def test_idea_explanation_stub_ignores_non_idea_context_payload() -> None:
    assert build_idea_explanation_stub_result(context_payload={}) is None


def test_idea_explanation_stub_coerces_malformed_lists_to_empty_output() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    cast(dict[str, Any], payload["redacted_evidence_packet"])["reason_codes"] = "not-a-list"
    cast(dict[str, Any], payload["explanation_request"])["requested_outputs"] = "not-a-list"

    result = build_idea_explanation_stub_result(context_payload=payload)

    assert result is not None
    _, structured_output = result
    assert structured_output["reason_codes"] == []
    assert structured_output["requested_outputs"] == []


def test_idea_explanation_stub_emits_consumer_idea_workflow_output_contract() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())

    result = build_idea_explanation_stub_result(context_payload=payload)

    assert result is not None
    message, structured_output = result
    output = cast(dict[str, Any], structured_output["idea_workflow_output"])
    assert output["output_id"] == "idea-explanation-output-idea-explanation-request-001"
    assert output["explanation_text"] == message
    claims = cast(list[dict[str, Any]], output["claims"])
    assert [claim["claim_id"] for claim in claims] == [
        "reason-01-high_cash_weight",
        "reason-02-benchmark_drift_attention",
    ]
    assert all(
        claim["source_product_ids"] == ["core-position-snapshot", "risk-concentration-snapshot"]
        for claim in claims
    )
    assert "HIGH_CASH_WEIGHT" in claims[0]["claim_text"]
    assert "idea-score-policy.v1" in claims[0]["claim_text"]
    assert output["proposed_actions"] == [
        {"action_type": "advisor_review", "action_label": "Review the evidence"}
    ]


def test_idea_explanation_stub_workflow_output_without_reason_codes_states_score_policy() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    cast(dict[str, Any], payload["redacted_evidence_packet"])["reason_codes"] = []

    result = build_idea_explanation_stub_result(context_payload=payload)

    assert result is not None
    _, structured_output = result
    output = cast(dict[str, Any], structured_output["idea_workflow_output"])
    claims = cast(list[dict[str, Any]], output["claims"])
    assert [claim["claim_id"] for claim in claims] == ["score-policy"]
    assert "idea-score-policy.v1" in claims[0]["claim_text"]


def test_idea_explanation_stub_workflow_output_requests_evidence_when_refs_missing() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    evidence = cast(dict[str, Any], payload["redacted_evidence_packet"])
    evidence["source_refs"] = ["not-a-ref", {"product_id": "   "}]
    cast(dict[str, Any], payload["explanation_request"])["request_id"] = ""

    result = build_idea_explanation_stub_result(context_payload=payload)

    assert result is not None
    _, structured_output = result
    output = cast(dict[str, Any], structured_output["idea_workflow_output"])
    assert output["output_id"] == "idea-explanation-output"
    claims = cast(list[dict[str, Any]], output["claims"])
    assert all(claim["source_product_ids"] == [] for claim in claims)
    assert output["proposed_actions"] == [
        {"action_type": "advisor_review", "action_label": "Review the evidence"},
        {
            "action_type": "request_missing_evidence",
            "action_label": "Request the missing governed evidence",
        },
    ]


def test_idea_explanation_stub_workflow_output_deduplicates_product_ids_and_replays() -> None:
    payload = cast(dict[str, Any], idea_explanation_payload())
    evidence = cast(dict[str, Any], payload["redacted_evidence_packet"])
    refs = cast(list[dict[str, Any]], evidence["source_refs"])
    evidence["source_refs"] = refs + [dict(refs[0])]

    first = build_idea_explanation_stub_result(context_payload=payload)
    second = build_idea_explanation_stub_result(context_payload=payload)

    assert first is not None
    assert first == second
    _, structured_output = first
    output = cast(dict[str, Any], structured_output["idea_workflow_output"])
    claims = cast(list[dict[str, Any]], output["claims"])
    assert claims[0]["source_product_ids"] == [
        "core-position-snapshot",
        "risk-concentration-snapshot",
    ]
