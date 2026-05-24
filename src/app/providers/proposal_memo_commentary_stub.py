from __future__ import annotations

from typing import Any


def build_proposal_memo_commentary_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    memo_evidence = context_payload.get("memo_evidence")
    commentary_request = context_payload.get("commentary_request")
    supportability = context_payload.get("supportability")
    if not isinstance(memo_evidence, dict) or not isinstance(commentary_request, dict):
        return None

    memo_id = _as_str(memo_evidence.get("memo_id"))
    memo_hash = _as_str(memo_evidence.get("memo_hash"))
    memo_status = _as_str(memo_evidence.get("memo_status"))
    requested_sections = commentary_request.get("requested_sections")
    source_refs = memo_evidence.get("source_refs")
    source_ref_count = len(source_refs) if isinstance(source_refs, list) else 0
    sections = _build_sections(requested_sections=requested_sections, memo_status=memo_status)

    message = (
        "Drafted review-gated advisor proposal memo commentary from bounded memo evidence "
        f"for memo {memo_id}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": "proposal_memo_commentary",
        "narrative_type": "advisor_proposal_memo_commentary",
        "state": "REVIEW_REQUIRED",
        "scope": "advisor_use_only",
        "memo_id": memo_id,
        "memo_hash": memo_hash,
        "memo_status": memo_status,
        "source_ref_count": source_ref_count,
        "sections": sections,
        "section_count": len(sections),
        "unsupported_claims": _unsupported_claims(supportability),
        "review_guidance": [
            "Review generated commentary against the persisted memo hash before advisor use.",
            "Do not treat commentary as suitability, approval, client-ready publication, or evidence mutation.",
            "Escalate missing policy, fee, tax, conflict, or eligibility evidence instead of asking AI to infer it.",
        ],
    }
    return message, structured_output


def _build_sections(*, requested_sections: object, memo_status: str) -> list[dict[str, str]]:
    section_keys = (
        [item for item in requested_sections if isinstance(item, str) and item.strip()]
        if isinstance(requested_sections, list)
        else []
    )
    if not section_keys:
        section_keys = ["EXECUTIVE_SUMMARY", "REVIEW_LIMITATIONS"]
    return [
        {
            "section_key": section_key,
            "title": _title(section_key),
            "text": (
                f"Advisor-use commentary for {section_key.lower().replace('_', ' ')} is "
                f"bounded to the supplied memo evidence. Current memo evidence posture is {memo_status}."
            ),
        }
        for section_key in section_keys[:8]
    ]


def _title(section_key: str) -> str:
    return section_key.replace("_", " ").title()


def _unsupported_claims(supportability: object) -> list[str]:
    if not isinstance(supportability, dict):
        return []
    value = supportability.get("unsupported_claims")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""
