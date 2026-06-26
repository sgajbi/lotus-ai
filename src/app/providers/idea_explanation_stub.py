from __future__ import annotations

from typing import Any


def build_idea_explanation_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    redacted_evidence = context_payload.get("redacted_evidence_packet")
    explanation_request = context_payload.get("explanation_request")
    supportability = context_payload.get("supportability")
    if not (
        isinstance(redacted_evidence, dict)
        and isinstance(explanation_request, dict)
        and isinstance(supportability, dict)
    ):
        return None

    candidate_id = _as_str(redacted_evidence.get("candidate_id"))
    evidence_packet_id = _as_str(redacted_evidence.get("evidence_packet_id"))
    source_refs = redacted_evidence.get("source_refs")
    reason_codes = _string_list(redacted_evidence.get("reason_codes"))
    requested_outputs = _string_list(explanation_request.get("requested_outputs"))

    message = (
        "Drafted a review-gated Lotus Idea explanation from redacted evidence packet "
        f"{evidence_packet_id} for candidate {candidate_id}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": "idea_explanation",
        "state": "REVIEW_REQUIRED",
        "scope": "advisor_and_reviewer_use_only",
        "candidate_id": candidate_id,
        "evidence_packet_id": evidence_packet_id,
        "evidence_content_hash": _as_str(redacted_evidence.get("evidence_content_hash")),
        "family": _as_str(redacted_evidence.get("family")),
        "lifecycle_status": _as_str(redacted_evidence.get("lifecycle_status")),
        "review_posture": _as_str(redacted_evidence.get("review_posture")),
        "source_ref_count": len(source_refs) if isinstance(source_refs, list) else 0,
        "source_signal_count": _int_or_zero(redacted_evidence.get("source_signal_count")),
        "reason_codes": reason_codes,
        "requested_outputs": requested_outputs,
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
    return message, structured_output


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0
