from __future__ import annotations

from typing import Any


def build_idea_service_envelope(
    context_payload: dict[str, object],
) -> dict[str, object] | None:
    """The SERVICE-OWNED portion of an idea-explanation output (issue #330).

    Every field here derives deterministically from the caller's context
    payload - identity, posture, authority blocks, review guidance. Both the
    stub and the live path compose over this one envelope, which is what
    makes it impossible for provenance or authority facts to come from model
    prose: the model authors only ``idea_workflow_output``.
    """

    redacted_evidence = context_payload.get("redacted_evidence_packet")
    explanation_request = context_payload.get("explanation_request")
    supportability = context_payload.get("supportability")
    if not (
        isinstance(redacted_evidence, dict)
        and isinstance(explanation_request, dict)
        and isinstance(supportability, dict)
    ):
        return None

    source_refs = redacted_evidence.get("source_refs")
    return {
        "workflow_pack_family": "idea_explanation",
        "state": "REVIEW_REQUIRED",
        "scope": "advisor_and_reviewer_use_only",
        "candidate_id": _as_str(redacted_evidence.get("candidate_id")),
        "evidence_packet_id": _as_str(redacted_evidence.get("evidence_packet_id")),
        "evidence_content_hash": _as_str(redacted_evidence.get("evidence_content_hash")),
        "family": _as_str(redacted_evidence.get("family")),
        "lifecycle_status": _as_str(redacted_evidence.get("lifecycle_status")),
        "review_posture": _as_str(redacted_evidence.get("review_posture")),
        "source_ref_count": len(source_refs) if isinstance(source_refs, list) else 0,
        "source_signal_count": _int_or_zero(redacted_evidence.get("source_signal_count")),
        "score_policy_version": _as_str(redacted_evidence.get("score_policy_version")),
        "reason_codes": _string_list(redacted_evidence.get("reason_codes")),
        "requested_outputs": _string_list(explanation_request.get("requested_outputs")),
        "purpose": _as_str(explanation_request.get("purpose")),
        "evaluation_ref": _as_str(explanation_request.get("evaluation_ref")),
        "human_review_required": True,
        "client_ready_publication": "BLOCKED",
        "downstream_authority": "BLOCKED",
        "unsupported_claims": _string_list(supportability.get("unsupported_claims")),
        "forbidden_actions": _string_list(supportability.get("forbidden_actions")),
        "review_guidance": [
            "Review the generated explanation against the redacted evidence packet before advisor use.",
            "Do not treat the explanation as suitability approval, final advice, rebalance authority, or client-ready communication.",
            "Escalate missing or unsupported evidence back to the source-owning Lotus service.",
        ],
    }


def packet_source_product_ids(context_payload: dict[str, object]) -> list[str]:
    """The product ids the evidence packet itself names - the ONLY ids a
    claim may ground in (issue #330)."""

    redacted_evidence = context_payload.get("redacted_evidence_packet")
    if not isinstance(redacted_evidence, dict):
        return []
    return _source_product_ids(redacted_evidence.get("source_refs"))


def build_idea_explanation_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    envelope = build_idea_service_envelope(context_payload)
    if envelope is None:
        return None

    redacted_evidence = context_payload.get("redacted_evidence_packet")
    explanation_request = context_payload.get("explanation_request")
    assert isinstance(redacted_evidence, dict)
    assert isinstance(explanation_request, dict)

    candidate_id = _as_str(redacted_evidence.get("candidate_id"))
    evidence_packet_id = _as_str(redacted_evidence.get("evidence_packet_id"))
    message = (
        "Drafted a review-gated Lotus Idea explanation from redacted evidence packet "
        f"{evidence_packet_id} for candidate {candidate_id}."
    )
    structured_output: dict[str, object] = dict(envelope)
    structured_output["idea_workflow_output"] = _idea_workflow_output(
        message=message,
        request_id=_as_str(explanation_request.get("request_id")),
        candidate_id=candidate_id,
        score_policy_version=_as_str(redacted_evidence.get("score_policy_version")),
        reason_codes=_string_list(redacted_evidence.get("reason_codes")),
        source_product_ids=packet_source_product_ids(context_payload),
    )
    return message, structured_output


def _idea_workflow_output(
    *,
    message: str,
    request_id: str,
    candidate_id: str,
    score_policy_version: str,
    reason_codes: list[str],
    source_product_ids: list[str],
) -> dict[str, object]:
    """Deterministic output in the consumer's shipped idea_workflow_output contract.

    lotus-idea's map_lotus_ai_idea_workflow_output requires explanation_text to equal
    the execution message, claims grounded only in the packet's own product ids, and
    proposed actions whose labels satisfy its strict action-policy patterns.
    """
    if reason_codes:
        claims: list[dict[str, object]] = [
            {
                "claim_id": f"reason-{index:02d}-{code.lower()}",
                "claim_text": (
                    f"Candidate {candidate_id} was surfaced with reason code {code} "
                    f"under scoring policy {score_policy_version}."
                ),
                "source_product_ids": source_product_ids,
            }
            for index, code in enumerate(reason_codes, start=1)
        ]
    else:
        claims = [
            {
                "claim_id": "score-policy",
                "claim_text": (
                    f"Candidate {candidate_id} was surfaced by deterministic "
                    f"scoring policy {score_policy_version}."
                ),
                "source_product_ids": source_product_ids,
            }
        ]
    proposed_actions: list[dict[str, object]] = [
        {"action_type": "advisor_review", "action_label": "Review the evidence"}
    ]
    if not source_product_ids:
        proposed_actions.append(
            {
                "action_type": "request_missing_evidence",
                "action_label": "Request the missing governed evidence",
            }
        )
    return {
        "output_id": (
            f"idea-explanation-output-{request_id}" if request_id else "idea-explanation-output"
        ),
        "explanation_text": message,
        "claims": claims,
        "proposed_actions": proposed_actions,
    }


def _source_product_ids(source_refs: object) -> list[str]:
    if not isinstance(source_refs, list):
        return []
    product_ids: list[str] = []
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        product_id = _as_str(ref.get("product_id"))
        if product_id and product_id not in product_ids:
            product_ids.append(product_id)
    return product_ids


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0
