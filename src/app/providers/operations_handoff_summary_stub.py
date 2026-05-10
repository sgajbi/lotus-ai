from __future__ import annotations

from typing import Any

from app.services.portfolio_memory_context_guardrails import portfolio_memory_context_summary


def build_operations_handoff_summary_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    wave_report_input = context_payload.get("wave_report_input")
    summary_request = context_payload.get("handoff_summary_request")
    supportability = context_payload.get("supportability")
    if not isinstance(wave_report_input, dict) or not isinstance(summary_request, dict):
        return None

    requested_outputs = summary_request.get("requested_outputs")
    items = wave_report_input.get("items")
    handoff_refs = wave_report_input.get("handoff_refs")
    source_refs = wave_report_input.get("source_refs")
    forbidden_actions = (
        supportability.get("forbidden_actions") if isinstance(supportability, dict) else []
    )

    wave_id = _as_str(wave_report_input.get("wave_id"))
    wave_state = _as_str(wave_report_input.get("wave_state"))
    content_hash = _as_str(wave_report_input.get("content_hash"))
    item_count = len(items) if isinstance(items, list) else 0
    handoff_ref_count = len(handoff_refs) if isinstance(handoff_refs, list) else 0
    source_ref_count = len(source_refs) if isinstance(source_refs, list) else 0
    blocked_item_count = _blocked_item_count(items)
    portfolio_memory_summary = portfolio_memory_context_summary(context_payload)

    message = (
        "Drafted a review-gated DPM operations handoff summary from bounded manage wave "
        f"handoff evidence for wave {wave_id} in state {wave_state}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": "dpm_operations_handoff_summary",
        "narrative_type": "operations_handoff_summary",
        "state": "REVIEW_REQUIRED",
        "scope": "support_only",
        "wave_id": wave_id,
        "wave_state": wave_state,
        "wave_report_content_hash": content_hash,
        "requested_outputs": requested_outputs if isinstance(requested_outputs, list) else [],
        "item_count": item_count,
        "blocked_item_count": blocked_item_count,
        "handoff_ref_count": handoff_ref_count,
        "source_ref_count": source_ref_count,
        "external_execution_claimed": bool(wave_report_input.get("external_execution_claimed")),
        "forbidden_actions": forbidden_actions if isinstance(forbidden_actions, list) else [],
        **portfolio_memory_summary,
        "unsupported_claims": _unsupported_claims(supportability),
        "review_guidance": [
            "Review the handoff summary against the source wave report hash before operations use.",
            "Do not treat this summary as order placement, routing instruction, or external execution acknowledgement.",
            "Escalate missing handoff refs, proof-pack refs, or source evidence instead of inferring prerequisites.",
            "Use portfolio memory only as bounded source lineage; do not reconstruct missing facts.",
        ],
    }
    return message, structured_output


def _blocked_item_count(items: object) -> int:
    if not isinstance(items, list):
        return 0
    return sum(
        1
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("state"), str)
        and item["state"] in {"BLOCKED", "EXCLUDED", "CANCELLED"}
    )


def _unsupported_claims(supportability: object) -> list[str]:
    if not isinstance(supportability, dict):
        return []
    value = supportability.get("unsupported_claims")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""
