from __future__ import annotations

import json
from copy import deepcopy
from typing import cast

import pytest
from fastapi import HTTPException

from app.contracts.providers import ProviderExecutionRequest
from app.providers.advisory_copilot_stub import build_advisory_copilot_stub_result
from app.providers.stub_text_provider import StubTextProvider
from app.services.provider_execution_config import resolve_provider_execution_config
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
    sections = cast(list[dict[str, object]], structured_output["sections"])
    section = sections[0]
    section_text = cast(str, section["text"])
    section_claims = cast(list[dict[str, object]], section["claims"])
    assert "policy_eval_sg_001" not in section_text
    assert "PB_SG_GLOBAL_BAL_001" not in section_text
    assert section_claims[0]["source_refs"] == [
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
    sections = cast(list[dict[str, object]], structured_output["sections"])
    section_claims = cast(list[dict[str, object]], sections[0]["claims"])
    assert section_claims[0]["source_refs"] == [
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


def test_advisory_copilot_identity_helper_follows_the_approved_identity() -> None:
    """Issue #126, helper scope only.

    This exercises `_advisory_copilot_model_risk_identity` directly. It proves
    the helper reads the approved provider and model version out of the
    structured output rather than substituting a local default, and nothing
    more. It is NOT evidence that an executed response agrees with its audit
    record, and it is not evidence about a real provider: the identity here is
    supplied by the test and echoed back.

    The response-level agreement is pinned by
    test_advisory_copilot_response_identity_matches_the_record_it_carries, and
    real-provider identity has to come from verified execution, which no stub
    can supply.
    """

    from app.providers.stub_text_provider import _advisory_copilot_model_risk_identity

    approved: dict[str, object] = {
        "model_risk": {
            "approved_provider_id": "lotus-ai",
            "approved_model_version": "lotus-ai-governed-model.v1",
        }
    }
    assert _advisory_copilot_model_risk_identity(approved) == (
        "lotus-ai",
        "lotus-ai-governed-model.v1",
    )

    # A different approved identity must be followed, not overridden by a
    # local default - otherwise the executed identity is the producer's
    # opinion rather than the approval.
    other: dict[str, object] = {
        "model_risk": {
            "approved_provider_id": "lotus-ai-alternate",
            "approved_model_version": "lotus-ai-governed-model.v2",
        }
    }
    assert _advisory_copilot_model_risk_identity(other) == (
        "lotus-ai-alternate",
        "lotus-ai-governed-model.v2",
    )


def test_advisory_copilot_response_identity_matches_the_record_it_carries() -> None:
    """Issue #126, at the boundary the original failure occurred on.

    Advise fail-closed with `MODEL_IDENTITY_SOURCE_DISAGREEMENT` and a
    `COPILOT_MODEL_IDENTITY_MISMATCH` fallback because the executed identity on
    the response disagreed with the approved identity in the structured record
    accompanying it. That is a property of the response object, so this drives
    the provider through its public `execute` entry point and compares the two
    fields Advise compares, rather than asserting a helper's return value.

    Scope, stated plainly: this proves the producer emits an internally
    consistent response. It does not prove a real provider executed under that
    identity - the adapter is a stub, `stubbed` is True, and an approved
    identity echoed by a stub is not execution attestation. That evidence has
    to come from verified live execution and is tracked outside this test.
    """

    request = ProviderExecutionRequest.model_validate(
        {
            "task_id": "explain.v1",
            "caller_app": "lotus-advise",
            "requested_by": "advisor.reviewer@lotus",
            "tenant_id": "tenant-sg-001",
            "prompt_version": "advisory-copilot-proposal-explanation.v1",
            "system_instructions": "Explain bounded advisory posture only.",
            "output_contract_notes": "Do not emit suitability approval.",
            "output_label": "EXPLANATION_ONLY",
            "safety_mode": "documented_only",
            "redaction_posture": "MINIMIZATION_REQUIRED",
            "context_summary": "Explain governed advisory copilot posture.",
            "context_payload": _payload(),
            "source_refs": [],
            "timeout_ms": 4000,
            "retry_limit": 0,
            "max_output_tokens": 512,
        }
    )

    response = StubTextProvider().execute(request, config=resolve_provider_execution_config())
    model_risk = cast(dict[str, object], response.structured_output["model_risk"])

    # The two fields Advise compares, taken from the same response.
    assert response.provider_id == model_risk["approved_provider_id"]
    assert response.model_version == model_risk["approved_model_version"]

    # And it is the approval that decides, not a default that happens to
    # match. The descriptor's own provider id is different, so a response
    # falling back to it would still be internally consistent with nothing.
    assert response.provider_id != StubTextProvider.descriptor.provider_id

    # The stub is labelled as one. This is the fact that stops the assertion
    # above being read as execution attestation.
    assert response.stubbed is True


def test_advisory_copilot_response_identity_follows_a_changed_approval() -> None:
    """The agreement above must come from the approval, not from a constant.

    Two values can agree because one is derived from the other, or because
    both happen to be the same literal. Changing the approved identity and
    requiring the response to move with it separates those, which a single
    fixed-value assertion cannot.
    """

    payload = _payload()
    _dict_at(payload, "model_risk_controls")["approved_provider_id"] = "lotus-ai-alternate"
    _dict_at(payload, "model_risk_controls")["approved_model_version"] = (
        "lotus-ai-governed-model.v9"
    )

    request = ProviderExecutionRequest.model_validate(
        {
            "task_id": "explain.v1",
            "caller_app": "lotus-advise",
            "requested_by": "advisor.reviewer@lotus",
            "tenant_id": "tenant-sg-001",
            "prompt_version": "advisory-copilot-proposal-explanation.v1",
            "system_instructions": "Explain bounded advisory posture only.",
            "output_contract_notes": "Do not emit suitability approval.",
            "output_label": "EXPLANATION_ONLY",
            "safety_mode": "documented_only",
            "redaction_posture": "MINIMIZATION_REQUIRED",
            "context_summary": "Explain governed advisory copilot posture.",
            "context_payload": payload,
            "source_refs": [],
            "timeout_ms": 4000,
            "retry_limit": 0,
            "max_output_tokens": 512,
        }
    )

    response = StubTextProvider().execute(request, config=resolve_provider_execution_config())
    model_risk = cast(dict[str, object], response.structured_output["model_risk"])

    assert model_risk["approved_provider_id"] == "lotus-ai-alternate"
    assert response.provider_id == "lotus-ai-alternate"
    assert response.model_version == "lotus-ai-governed-model.v9"


def test_advisory_copilot_absent_approval_is_not_replaced_by_a_plausible_identity() -> None:
    """Absence must surface as absence, so the mismatch is visible downstream.

    The producer and the consumer split this refusal. lotus-ai never fabricates
    an approved identity: with no approval present it falls back to the stub's
    own descriptor id and a null model version. Advise then sees an executed
    identity that does not match an approved one and fail-closes with
    `MODEL_IDENTITY_SOURCE_DISAGREEMENT`.

    The dangerous alternative is the producer filling the gap with something
    that looks approved - the last approved value, a configured default, the
    descriptor id presented as though it were the approval. That would make the
    two fields agree and remove the consumer's only signal, converting a
    fail-closed refusal into a silent pass. This pins that the gap stays a gap.
    """

    payload = _payload()
    controls = _dict_at(payload, "model_risk_controls")
    controls["approved_provider_id"] = ""
    controls["approved_model_version"] = ""

    request = ProviderExecutionRequest.model_validate(
        {
            "task_id": "explain.v1",
            "caller_app": "lotus-advise",
            "requested_by": "advisor.reviewer@lotus",
            "tenant_id": "tenant-sg-001",
            "prompt_version": "advisory-copilot-proposal-explanation.v1",
            "system_instructions": "Explain bounded advisory posture only.",
            "output_contract_notes": "Do not emit suitability approval.",
            "output_label": "EXPLANATION_ONLY",
            "safety_mode": "documented_only",
            "redaction_posture": "MINIMIZATION_REQUIRED",
            "context_summary": "Explain governed advisory copilot posture.",
            "context_payload": payload,
            "source_refs": [],
            "timeout_ms": 4000,
            "retry_limit": 0,
            "max_output_tokens": 512,
        }
    )

    response = StubTextProvider().execute(request, config=resolve_provider_execution_config())
    model_risk = cast(dict[str, object], response.structured_output["model_risk"])

    # No approval was stated, so none is claimed.
    assert not model_risk["approved_provider_id"]
    assert not model_risk["approved_model_version"]

    # The executed identity falls back to the adapter's own, and the model
    # version stays null rather than borrowing a previously approved one.
    assert response.provider_id == StubTextProvider.descriptor.provider_id
    assert response.model_version is None

    # The two disagree, which is the whole point: a consumer comparing them
    # has something to refuse on.
    assert response.provider_id != model_risk["approved_provider_id"]
