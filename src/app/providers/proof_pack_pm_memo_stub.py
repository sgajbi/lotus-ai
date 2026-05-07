from __future__ import annotations

from typing import Any


def build_proof_pack_pm_memo_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    ai_evidence = context_payload.get("ai_evidence_input")
    memo_request = context_payload.get("memo_request")
    supportability = context_payload.get("supportability")
    if not isinstance(ai_evidence, dict) or not isinstance(memo_request, dict):
        return None

    requested_outputs = memo_request.get("requested_outputs")
    sections = ai_evidence.get("sections")
    source_refs = ai_evidence.get("source_refs")
    forbidden_actions = ai_evidence.get("forbidden_actions")
    forbidden_fields_removed = ai_evidence.get("forbidden_fields_removed")

    proof_pack_id = _as_str(ai_evidence.get("proof_pack_id"))
    portfolio_id = _as_str(ai_evidence.get("portfolio_id"))
    content_hash = _as_str(ai_evidence.get("content_hash"))
    proof_pack_content_hash = _as_str(ai_evidence.get("proof_pack_content_hash"))
    supportability_status = _as_str(ai_evidence.get("supportability_status"))
    output_count = len(requested_outputs) if isinstance(requested_outputs, list) else 0
    section_count = len(sections) if isinstance(sections, list) else 0
    source_count = len(source_refs) if isinstance(source_refs, list) else 0

    message = (
        "Drafted a review-gated DPM proof-pack PM memo from bounded manage AI evidence "
        f"for portfolio {portfolio_id} and proof pack {proof_pack_id}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": "dpm_pm_memo",
        "narrative_type": "proof_pack_pm_memo",
        "state": "REVIEW_REQUIRED",
        "scope": "support_only",
        "proof_pack_id": proof_pack_id,
        "portfolio_id": portfolio_id,
        "proof_pack_content_hash": proof_pack_content_hash,
        "ai_evidence_content_hash": content_hash,
        "supportability_status": supportability_status,
        "requested_outputs": requested_outputs if isinstance(requested_outputs, list) else [],
        "section_count": section_count,
        "source_ref_count": source_count,
        "output_count": output_count,
        "forbidden_actions": forbidden_actions if isinstance(forbidden_actions, list) else [],
        "forbidden_fields_removed": (
            forbidden_fields_removed if isinstance(forbidden_fields_removed, list) else []
        ),
        "unsupported_claims": _unsupported_claims(supportability),
        "review_guidance": [
            "Review the memo against the source proof-pack hash before using it in PM workflow.",
            "Do not treat this memo as trade approval, client communication, or order instruction.",
            "Escalate missing evidence instead of asking the model to infer it.",
        ],
    }
    return message, structured_output


def _unsupported_claims(supportability: object) -> list[str]:
    if not isinstance(supportability, dict):
        return []
    value = supportability.get("unsupported_claims")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""
