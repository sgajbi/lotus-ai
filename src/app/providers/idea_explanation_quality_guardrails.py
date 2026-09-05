"""Live idea-explanation output normalization (issue #330, audit F6).

The live shaper previously parsed domain JSON only for advisor briefs; an
Idea answer stayed a raw message and could never satisfy the registered
`idea_explanation.pack.v1` contract. This module closes that: the SERVICE
composes every provenance/authority field from the caller's context payload
(`build_idea_service_envelope` - shared with the stub), and the model
authors ONLY `idea_workflow_output`, which is validated here for the
semantic layer the JSON Schema cannot express:

- every claim's ``source_product_ids`` must be a subset of the product ids
  the evidence packet itself names - a fabricated reference refuses;
- a contract failure NEVER manufactures a plausible explanation: the result
  omits ``idea_workflow_output`` entirely, so the one deterministic output
  validator rejects the output whole with the pack contract as authority.

Shape and vocabulary stay schema-enforced (`additionalProperties: false`,
``action_type`` enum) - this module does not duplicate the schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.idea_explanation_stub import (
    build_idea_service_envelope,
    packet_source_product_ids,
)

REFUSAL_MISSING_VALID_JSON = "missing_valid_json"
REFUSAL_STRICT_JSON_SALVAGED = "strict_json_salvaged"
REFUSAL_MISSING_WORKFLOW_OUTPUT = "missing_idea_workflow_output"
REFUSAL_MISSING_EXPLANATION_TEXT = "missing_explanation_text"
REFUSAL_UNGROUNDED_CLAIM = "ungrounded_claim_product_ids"
REFUSAL_INCOMPLETE_WORKFLOW_OUTPUT = "incomplete_idea_workflow_output"


@dataclass(frozen=True)
class IdeaExplanationQualityResult:
    """The normalized outcome: either the full contract-shaped output, or a
    refusal that withholds the model-authored section so the validator can
    reject against the registered pack contract."""

    message: str
    structured_output: dict[str, Any]
    refusal_reason: str | None


def is_idea_explanation_payload(payload: dict[str, Any]) -> bool:
    return {"redacted_evidence_packet", "explanation_request", "supportability"}.issubset(
        payload.keys()
    )


def normalize_idea_explanation_output(
    *,
    parsed_output: dict[str, Any] | None,
    salvaged: bool,
    output_message: str,
    context_payload: dict[str, Any],
) -> IdeaExplanationQualityResult | None:
    """Compose envelope + validated model-authored section, or refuse.

    Returns None only when the payload is not an idea-explanation request
    at all (the caller gates on ``is_idea_explanation_payload`` first, so
    this is defensive).
    """

    envelope = build_idea_service_envelope(context_payload)
    if envelope is None:
        return None

    def _refusal(reason: str) -> IdeaExplanationQualityResult:
        # Never manufacture: the model-authored section is simply absent,
        # and the registered pack contract - the single output authority -
        # rejects the output whole downstream.
        return IdeaExplanationQualityResult(
            message=output_message,
            structured_output=dict(envelope),
            refusal_reason=reason,
        )

    if parsed_output is None:
        return _refusal(REFUSAL_MISSING_VALID_JSON)
    if salvaged:
        # A governed pack answer that needed salvage repair is not strict
        # JSON evidence. DELIBERATE sibling difference from the advisor
        # brief (which marks strict_json_salvaged and lets the profile
        # decide, so local runs survive as UNVALIDATED_LOCAL_ONLY): idea
        # explanations serve a restricted-tenant, review-gated family, and
        # refusing salvage outright in EVERY profile keeps local behavior
        # identical to promoted rather than softer.
        return _refusal(REFUSAL_STRICT_JSON_SALVAGED)

    raw_workflow_output = parsed_output.get("idea_workflow_output")
    if not isinstance(raw_workflow_output, dict):
        return _refusal(REFUSAL_MISSING_WORKFLOW_OUTPUT)

    explanation_text = raw_workflow_output.get("explanation_text")
    if not isinstance(explanation_text, str) or not explanation_text.strip():
        return _refusal(REFUSAL_MISSING_EXPLANATION_TEXT)
    explanation_text = explanation_text.strip()

    # The consumer's shipped mapper (lotus-idea
    # map_lotus_ai_idea_workflow_output) routes output_id, claim_id,
    # claim_text and action_label through _text() - strip + non-empty - and
    # refuses empty claims/actions and any claim without non-empty
    # source_product_ids. JSON Schema minLength counts whitespace, so the
    # whitespace-only class is enforced HERE: an accepted live output can
    # never fail the consumer boundary. Accepted text fields are stored
    # STRIPPED (edge-only, internal whitespace preserved) so the archived
    # producer evidence equals what the consumer records.
    output_id = raw_workflow_output.get("output_id")
    claims = raw_workflow_output.get("claims")
    proposed_actions = raw_workflow_output.get("proposed_actions")
    if (
        not (isinstance(output_id, str) and output_id.strip())
        or not (isinstance(claims, list) and claims)
        or not (isinstance(proposed_actions, list) and proposed_actions)
        or any(not isinstance(claim, dict) for claim in claims)
        or any(not isinstance(action, dict) for action in proposed_actions)
    ):
        return _refusal(REFUSAL_INCOMPLETE_WORKFLOW_OUTPUT)

    grounded_ids = set(packet_source_product_ids(context_payload))
    normalized_claims: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = claim.get("claim_id")
        claim_text = claim.get("claim_text")
        claim_ids = claim.get("source_product_ids")
        if (
            not (isinstance(claim_id, str) and claim_id.strip())
            or not (isinstance(claim_text, str) and claim_text.strip())
            or not (isinstance(claim_ids, list) and claim_ids)
        ):
            return _refusal(REFUSAL_INCOMPLETE_WORKFLOW_OUTPUT)
        if any(
            not isinstance(product_id, str) or product_id not in grounded_ids
            for product_id in claim_ids
        ):
            return _refusal(REFUSAL_UNGROUNDED_CLAIM)
        normalized_claims.append(
            dict(claim, claim_id=claim_id.strip(), claim_text=claim_text.strip())
        )

    normalized_actions: list[dict[str, Any]] = []
    for action in proposed_actions:
        action_label = action.get("action_label")
        if not (isinstance(action_label, str) and action_label.strip()):
            return _refusal(REFUSAL_INCOMPLETE_WORKFLOW_OUTPUT)
        normalized_actions.append(dict(action, action_label=action_label.strip()))

    normalized_workflow_output = dict(raw_workflow_output)
    # The consumer requires explanation_text to EQUAL the served message;
    # normalizing the stored text to the same stripped value keeps that
    # equality exact rather than whitespace-lucky.
    normalized_workflow_output["explanation_text"] = explanation_text
    normalized_workflow_output["output_id"] = output_id.strip()
    normalized_workflow_output["claims"] = normalized_claims
    normalized_workflow_output["proposed_actions"] = normalized_actions

    structured_output: dict[str, Any] = dict(envelope)
    structured_output["idea_workflow_output"] = normalized_workflow_output
    return IdeaExplanationQualityResult(
        message=explanation_text,
        structured_output=structured_output,
        refusal_reason=None,
    )
