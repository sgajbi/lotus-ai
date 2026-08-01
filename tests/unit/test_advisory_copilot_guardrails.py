from __future__ import annotations

import json
from copy import deepcopy
from typing import cast

import pytest
from fastapi import HTTPException

from app.providers.advisory_copilot_stub import build_advisory_copilot_stub_result
from app.services.advisory_copilot_guardrails import validate_advisory_copilot_payload
from tests.support.workflow_pack_fixtures import advisory_copilot_payload


def test_validate_advisory_copilot_payload_accepts_bounded_evidence_packet() -> None:
    validate_advisory_copilot_payload(_payload())


@pytest.mark.parametrize(
    ("section_key", "detail"),
    [
        ("copilot_evidence_packet", "requires `copilot_evidence_packet`"),
        ("copilot_request", "requires `copilot_request`"),
        ("supportability", "requires `supportability`"),
        ("model_risk_controls", "requires `model_risk_controls`"),
    ],
)
def test_validate_advisory_copilot_payload_requires_governed_sections(
    section_key: str,
    detail: str,
) -> None:
    payload = _payload()
    payload[section_key] = None

    _assert_rejects(payload, detail)


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    [
        (
            "evidence_packet_hash",
            "copilot-evidence-packet-001",
            "must carry a sha256 content hash",
        ),
        (
            "client_ready_publication",
            "READY",
            "must keep client-ready publication blocked",
        ),
        (
            "sections",
            {"section_key": "POLICY_POSTURE"},
            "sections must be supplied as a list",
        ),
        (
            "unsupported_evidence",
            {"source": "restricted"},
            "unsupported evidence must be supplied as a list",
        ),
    ],
)
def test_validate_advisory_copilot_payload_rejects_invalid_evidence_packet(
    field: str,
    value: object,
    detail: str,
) -> None:
    payload = _payload()
    _dict_at(payload, "copilot_evidence_packet")[field] = value

    _assert_rejects(payload, detail)


def test_validate_advisory_copilot_payload_rejects_non_structured_evidence_sections() -> None:
    payload = _payload()
    _dict_at(payload, "copilot_evidence_packet")["sections"] = ["policy posture"]

    _assert_rejects(payload, "evidence sections must be structured objects")


def test_validate_advisory_copilot_payload_rejects_evidence_sections_without_sources() -> None:
    payload = _payload()
    section = _first_evidence_section(payload)
    section["source_refs"] = []

    _assert_rejects(payload, "evidence sections must carry source refs")


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    [
        ("action_family", "", "must include an action family"),
        ("audience", None, "must include an audience"),
        (
            "requested_outputs",
            "advisor_review_summary",
            "must include bounded requested outputs",
        ),
    ],
)
def test_validate_advisory_copilot_payload_rejects_invalid_request_shape(
    field: str,
    value: object,
    detail: str,
) -> None:
    payload = _payload()
    _dict_at(payload, "copilot_request")[field] = value

    _assert_rejects(payload, detail)


def test_validate_advisory_copilot_payload_rejects_empty_requested_outputs() -> None:
    payload = _payload()
    _dict_at(payload, "copilot_request")["requested_outputs"] = []

    _assert_rejects(payload, "must include bounded requested outputs")


def test_validate_advisory_copilot_payload_rejects_forbidden_requested_outputs() -> None:
    payload = _payload()
    _dict_at(payload, "copilot_request")["requested_outputs"] = [
        "advisor_review_summary",
        "client_ready_publication",
        "place_order",
    ]

    _assert_rejects(
        payload,
        "Forbidden advisory copilot outputs requested: client_ready_publication, place_order",
    )


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    [
        ("human_review_required", False, "must require human review"),
        (
            "client_ready_publication",
            "READY",
            "supportability must block client-ready publication",
        ),
        (
            "unsupported_claims",
            "policy_approval",
            "supportability must include unsupported claims",
        ),
    ],
)
def test_validate_advisory_copilot_payload_rejects_invalid_supportability(
    field: str,
    value: object,
    detail: str,
) -> None:
    payload = _payload()
    _dict_at(payload, "supportability")[field] = value

    _assert_rejects(payload, detail)


def test_validate_advisory_copilot_payload_requires_policy_trade_and_publication_limits() -> None:
    payload = _payload()
    _dict_at(payload, "supportability")["unsupported_claims"] = [
        "policy_approval",
        "trade_or_order_action",
    ]

    _assert_rejects(payload, "supportability is missing required unsupported claims")


def test_validate_advisory_copilot_payload_requires_model_risk_controls() -> None:
    payload = _payload()
    _dict_at(payload, "model_risk_controls")["evaluation_pack_ref"] = ""

    _assert_rejects(payload, "model-risk controls missing: evaluation_pack_ref")


def test_validate_advisory_copilot_payload_rejects_technical_leakage_anywhere() -> None:
    payload = _payload()
    _first_evidence_section(payload)["trace_id"] = "trace-should-not-leak"

    _assert_rejects(payload, "cannot include technical field `trace_id`")


def test_build_advisory_copilot_stub_result_returns_review_gated_output() -> None:
    result = build_advisory_copilot_stub_result(
        context_payload=_payload(),
        source_refs=[
            ("lotus-advise:POLICY_EVALUATION:policy_eval_sg_001:sha256:policy-evaluation")
        ],
    )

    assert result is not None
    message, structured_output = result
    assert "copilot_packet_pb_sg_001" in message
    assert structured_output["workflow_pack_family"] == "advisory_copilot_proposal_explanation"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "advisor_and_reviewer_use_only"
    assert structured_output["client_ready_publication"] == "BLOCKED"
    assert structured_output["human_review_required"] is True
    assert structured_output["section_count"] == 1
    section = structured_output["sections"][0]
    assert "policy_eval_sg_001" not in section["text"]
    assert "PB_SG_GLOBAL_BAL_001" not in section["text"]
    assert section["claims"][0]["source_refs"] == [
        "lotus-advise:POLICY_EVALUATION:policy_eval_sg_001:sha256:policy-evaluation"
    ]
    assert structured_output["unsupported_evidence_count"] == 0
    unsupported_claims = structured_output["unsupported_claims"]
    assert isinstance(unsupported_claims, list)
    assert "policy_approval" in unsupported_claims

    model_risk = structured_output["model_risk"]
    assert isinstance(model_risk, dict)
    assert model_risk["approved_provider_id"] == "lotus-ai"
    assert model_risk["approved_model_version"] == "lotus-ai-governed-model.v1"
    assert model_risk["evaluation_pack_ref"] == "advisory-copilot-eval-pack.v1"
    assert len(json.dumps(structured_output, sort_keys=True, separators=(",", ":"))) < 2500


def test_build_advisory_copilot_stub_result_preserves_no_content_hash_grounding() -> None:
    payload = _payload()
    evidence_packet = _dict_at(payload, "copilot_evidence_packet")
    evidence_packet["action_family"] = "OPERATIONS_REPORT_HANDOFF"
    evidence_packet["sections"] = [
        {
            "section_key": "OPERATIONS_HANDOFF",
            "title": "Operations handoff",
            "evidence_class": "OPERATIONS_HANDOFF_EVIDENCE",
            "summary_items": [
                "Latest implementation handoff posture is EXECUTION_READY.",
            ],
            "source_refs": [
                {
                    "source_system": "lotus-advise",
                    "source_type": "PROPOSAL_WORKFLOW_EVENT",
                    "source_ref_token": "tok_source-ref_001",
                    "content_hash": None,
                    "access_class": "OPERATIONS_HANDOFF_EVIDENCE",
                }
            ],
        }
    ]
    _dict_at(payload, "copilot_request")["action_family"] = "OPERATIONS_REPORT_HANDOFF"

    result = build_advisory_copilot_stub_result(
        context_payload=payload,
        source_refs=[
            "lotus-advise:PROPOSAL_WORKFLOW_EVENT:event_execution_ready_001:no-content-hash"
        ],
    )

    assert result is not None
    _, structured_output = result
    assert structured_output["workflow_pack_family"] == (
        "advisory_copilot_operations_report_handoff"
    )
    assert structured_output["section_count"] == 1
    assert structured_output["sections"][0]["claims"][0]["source_refs"] == [
        "lotus-advise:PROPOSAL_WORKFLOW_EVENT:event_execution_ready_001:no-content-hash"
    ]


def test_build_advisory_copilot_stub_result_requires_governed_context_sections() -> None:
    payload = _payload()
    payload["supportability"] = None

    assert build_advisory_copilot_stub_result(context_payload=payload) is None


def test_build_advisory_copilot_stub_result_ignores_unusable_sections_and_claims() -> None:
    payload = _payload()
    evidence_packet = _dict_at(payload, "copilot_evidence_packet")
    evidence_packet["unsupported_evidence"] = {"source": "restricted"}
    evidence_packet["sections"] = [
        "not structured",
        {"section_key": "MISSING_TITLE", "summary_items": ["No title"]},
        {
            "section_key": "MISSING_SUMMARY",
            "title": "Missing summary",
            "summary_items": ["", 123],
        },
    ]
    _dict_at(payload, "copilot_request")["action_family"] = "  "
    _dict_at(payload, "supportability")["unsupported_claims"] = [
        "policy_approval",
        "",
        100,
    ]

    result = build_advisory_copilot_stub_result(context_payload=payload)

    assert result is not None
    _, structured_output = result
    assert structured_output["workflow_pack_family"] == "advisory_copilot"
    assert structured_output["sections"] == []
    assert structured_output["section_count"] == 0
    assert structured_output["unsupported_evidence_count"] == 0
    assert structured_output["unsupported_claims"] == ["policy_approval"]


def _payload() -> dict[str, object]:
    return deepcopy(advisory_copilot_payload())


def _dict_at(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload[key]
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _first_evidence_section(payload: dict[str, object]) -> dict[str, object]:
    sections = _dict_at(payload, "copilot_evidence_packet")["sections"]
    assert isinstance(sections, list)
    first_section = sections[0]
    assert isinstance(first_section, dict)
    return cast(dict[str, object], first_section)


def _assert_rejects(payload: dict[str, object], detail: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_advisory_copilot_payload(payload)
    assert exc_info.value.status_code == 422
    assert detail in str(exc_info.value.detail)
