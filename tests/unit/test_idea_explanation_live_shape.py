"""Live Idea answers satisfy the registered pack contract (issue #330, F6).

The audit probe showed a perfectly-shaped live Idea answer still missing 29
required contract fields: only advisor briefs got domain parsing. These
tests pin the closure - the SAME consumer contract validates stub and live
outputs, service-owned provenance/authority never comes from model prose,
and a provider answer that fails the pack contract is refused whole, never
manufactured into a plausible explanation.
"""

from __future__ import annotations

import json
from typing import Any

from app.contracts.providers import ProviderExecutionRequest
from app.providers.idea_explanation_stub import build_idea_explanation_stub_result
from app.providers.local_openai_compatible_text_provider import (
    LocalOpenAICompatibleTextProvider,
)
from app.providers.openai_compatible_text_transport import build_structured_output
from app.services.output_contracts import schema_violations
from tests.support.workflow_pack_fixtures import idea_explanation_payload

_CONTRACT_KEY = "idea_explanation.pack"


def _request(context_payload: dict[str, object]) -> ProviderExecutionRequest:
    return ProviderExecutionRequest.model_validate(
        {
            "task_id": "explain.v1",
            "caller_app": "lotus-idea",
            "requested_by": "reviewer@lotus",
            "prompt_version": "foundation.explain.v1",
            "system_instructions": "Explain the idea candidate conservatively.",
            "output_contract_notes": "Return the idea explanation contract only.",
            "output_label": "EXPLANATION_ONLY",
            "safety_mode": "documented_only",
            "redaction_posture": "MINIMIZATION_REQUIRED",
            "context_summary": "Idea explanation for review",
            "context_payload": context_payload,
            "source_refs": ["lotus-idea:evidence:idea_evidence_high_cash_001"],
            "timeout_ms": 4000,
            "retry_limit": 0,
            "max_output_tokens": 512,
        }
    )


def _well_shaped_answer(**iwo_overrides: Any) -> str:
    iwo: dict[str, Any] = {
        "output_id": "idea-explanation-output-idea-explanation-request-001",
        "explanation_text": "The candidate was surfaced for high cash weight.",
        "claims": [
            {
                "claim_id": "claim-1",
                "claim_text": "Cash weight exceeds the policy band.",
                "source_product_ids": ["core-position-snapshot"],
            }
        ],
        "proposed_actions": [
            {"action_type": "advisor_review", "action_label": "Review the evidence"}
        ],
    }
    iwo.update(iwo_overrides)
    return json.dumps({"idea_workflow_output": iwo})


def _live_output(output_message: str) -> tuple[str, dict[str, Any]]:
    return build_structured_output(
        descriptor=LocalOpenAICompatibleTextProvider().descriptor,
        request=_request(idea_explanation_payload()),
        response_payload={"id": "resp_live", "model": "gpt-5.4", "usage": {}},
        output_message=output_message,
    )


def test_live_and_stub_outputs_satisfy_the_same_pack_contract() -> None:
    """The F6 closure itself: one consumer contract, both execution modes."""

    message, live = _live_output(_well_shaped_answer())
    assert schema_violations(_CONTRACT_KEY, live) == []
    # The consumer mapper requires explanation_text to equal the served
    # message - the live path returns the model's explanation as message.
    assert message == "The candidate was surfaced for high cash weight."
    assert live["idea_workflow_output"]["explanation_text"] == message

    stub_result = build_idea_explanation_stub_result(context_payload=idea_explanation_payload())
    assert stub_result is not None
    _, stub_envelope = stub_result
    # The stub adapter adds its own request echoes before validation; the
    # shared envelope + workflow output already validate through the
    # executed-pack conformance test. Here: the SERVICE envelope is
    # byte-identical between modes.
    for key, value in stub_envelope.items():
        if key == "idea_workflow_output":
            continue
        assert live[key] == value, key


def test_service_authority_fields_never_come_from_model_prose() -> None:
    """A model that emits authority fields at top level changes nothing:
    only idea_workflow_output is taken from the answer."""

    answer = json.dumps(
        {
            "client_ready_publication": "APPROVED",
            "downstream_authority": "GRANTED",
            "human_review_required": False,
            "idea_workflow_output": json.loads(_well_shaped_answer())["idea_workflow_output"],
        }
    )
    _, live = _live_output(answer)
    assert live["client_ready_publication"] == "BLOCKED"
    assert live["downstream_authority"] == "BLOCKED"
    assert live["human_review_required"] is True
    assert schema_violations(_CONTRACT_KEY, live) == []


def test_contract_failures_refuse_whole_and_never_manufacture() -> None:
    """Every refusal reason leaves the output missing idea_workflow_output,
    so the registered contract rejects it whole - no plausible explanation
    is ever synthesized from a failed provider answer."""

    failures = {
        "prose_not_json": "The candidate looks attractive because of cash.",
        "missing_workflow_output": json.dumps({"answer": "text"}),
        "missing_explanation_text": _well_shaped_answer(explanation_text="  "),
        "fabricated_reference": _well_shaped_answer(
            claims=[
                {
                    "claim_id": "claim-x",
                    "claim_text": "Grounded in a product the packet never named.",
                    "source_product_ids": ["fabricated-product-id"],
                }
            ]
        ),
    }
    for name, answer in failures.items():
        message, live = _live_output(answer)
        assert "idea_workflow_output" not in live, name
        violations = schema_violations(_CONTRACT_KEY, live)
        assert violations, name
        # The raw answer is passed through as the message for audit
        # evidence; it is never dressed up as a contract-shaped output.
        assert message == answer, name


def test_unsupported_actions_are_refused_by_the_contract_vocabulary() -> None:
    """The schema's action_type enum is the vocabulary authority: an
    unsupported action fails validation rather than being filtered into a
    plausible output."""

    _, live = _live_output(
        _well_shaped_answer(
            proposed_actions=[{"action_type": "place_orders", "action_label": "Buy now"}]
        )
    )
    # Shape-valid enough to pass the mapper (grounding holds), so the
    # section rides through - and the CONTRACT refuses the vocabulary. The
    # anyOf validator aggregates branch failures, so the pin is the refusal
    # itself: the section is present, yet the output does not validate.
    assert live["idea_workflow_output"]["proposed_actions"][0]["action_type"] == "place_orders"
    assert schema_violations(_CONTRACT_KEY, live)


def test_salvaged_json_refuses_and_non_idea_payloads_pass_through() -> None:
    """A governed pack answer needing salvage repair is not strict-JSON
    evidence - it refuses like any contract failure; and the normalizer is
    inert for payloads that are not idea-explanation requests at all."""

    from app.providers.idea_explanation_quality_guardrails import (
        normalize_idea_explanation_output,
    )

    salvaged = normalize_idea_explanation_output(
        parsed_output=json.loads(_well_shaped_answer()),
        salvaged=True,
        output_message=_well_shaped_answer(),
        context_payload=idea_explanation_payload(),
    )
    assert salvaged is not None
    assert salvaged.refusal_reason == "strict_json_salvaged"
    assert "idea_workflow_output" not in salvaged.structured_output

    assert (
        normalize_idea_explanation_output(
            parsed_output=None,
            salvaged=False,
            output_message="anything",
            context_payload={"unrelated": True},
        )
        is None
    )


def test_packet_product_ids_handle_malformed_evidence_shapes() -> None:
    from app.providers.idea_explanation_stub import packet_source_product_ids

    assert packet_source_product_ids({"redacted_evidence_packet": "not-a-dict"}) == []
    assert (
        packet_source_product_ids({"redacted_evidence_packet": {"source_refs": "not-a-list"}}) == []
    )


def test_accepted_live_output_satisfies_the_shipped_consumer_mapper() -> None:
    """Conformance against lotus-idea's map_lotus_ai_idea_workflow_output,
    mirrored from its shipped code (consumer-contract fidelity): non-empty
    output_id/claims/proposed_actions, every claim id/text/product-id list
    non-empty, and explanation_text EXACTLY equal to the served message -
    including when the model pads the text with whitespace."""

    message, live = _live_output(
        _well_shaped_answer(explanation_text="  The candidate was surfaced for high cash weight.  ")
    )
    workflow_output = live["idea_workflow_output"]
    assert workflow_output["explanation_text"] == message
    # STRIP-ONLY equality, exactly like the shipped mapper's _text(): edge
    # whitespace is trimmed, internal whitespace is preserved and
    # significant - collapsing internal runs would let the producer accept
    # pairs the shipped consumer refuses.
    internal_ws = "The candidate  was\tsurfaced for high cash weight."
    ws_message, ws_live = _live_output(_well_shaped_answer(explanation_text=f"  {internal_ws}  "))
    assert ws_message == internal_ws
    assert ws_live["idea_workflow_output"]["explanation_text"] == internal_ws
    # Execution-level facts the shipped mapper hard-fails on: the label
    # rides the structured output from the request, never from model prose.
    assert live["output_label"] == "EXPLANATION_ONLY"
    assert workflow_output["output_id"].strip()
    assert workflow_output["claims"] and workflow_output["proposed_actions"]
    for claim in workflow_output["claims"]:
        # Stored STRIPPED, exactly what the consumer's _text() records - the
        # producer archive and the consumer record cannot disagree.
        assert claim["claim_id"] == claim["claim_id"].strip() != ""
        assert claim["claim_text"] == claim["claim_text"].strip() != ""
        assert claim["source_product_ids"]
        assert all(product_id.strip() for product_id in claim["source_product_ids"])
    for action in workflow_output["proposed_actions"]:
        assert action["action_type"] in {"advisor_review", "request_missing_evidence"}
        assert action["action_label"] == action["action_label"].strip() != ""
    assert schema_violations(_CONTRACT_KEY, live) == []


def test_consumer_required_completeness_is_refused_when_absent() -> None:
    """The consumer refuses empty claims/actions/output_id and any claim
    without product ids - the live mapper refuses FIRST, so an accepted
    output can never fail the consumer boundary."""

    incomplete = {
        "empty_claims": _well_shaped_answer(claims=[]),
        "empty_actions": _well_shaped_answer(proposed_actions=[]),
        "missing_output_id": _well_shaped_answer(output_id="  "),
        "claim_without_product_ids": _well_shaped_answer(
            claims=[
                {
                    "claim_id": "claim-1",
                    "claim_text": "Ungroundable claim.",
                    "source_product_ids": [],
                }
            ]
        ),
        # The whitespace-only class (bb's F1 on the PR): JSON Schema
        # minLength counts whitespace, but the shipped consumer's _text()
        # refuses these - the producer must refuse them first.
        "whitespace_claim_text": _well_shaped_answer(
            claims=[
                {
                    "claim_id": "claim-1",
                    "claim_text": "  ",
                    "source_product_ids": ["core-position-snapshot"],
                }
            ]
        ),
        "whitespace_claim_id": _well_shaped_answer(
            claims=[
                {
                    "claim_id": " ",
                    "claim_text": "Cash weight exceeds the policy band.",
                    "source_product_ids": ["core-position-snapshot"],
                }
            ]
        ),
        "whitespace_action_label": _well_shaped_answer(
            proposed_actions=[{"action_type": "advisor_review", "action_label": "   "}]
        ),
    }
    for name, answer in incomplete.items():
        _, live = _live_output(answer)
        assert "idea_workflow_output" not in live, name
        assert schema_violations(_CONTRACT_KEY, live), name
