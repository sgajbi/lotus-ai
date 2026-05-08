from __future__ import annotations

from typing import Any

from app.services.portfolio_memory_context_guardrails import portfolio_memory_context_summary


def build_wave_pm_memo_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    wave_report_input = context_payload.get("wave_report_input")
    memo_request = context_payload.get("memo_request")
    supportability = context_payload.get("supportability")
    if not isinstance(wave_report_input, dict) or not isinstance(memo_request, dict):
        return None

    requested_outputs = memo_request.get("requested_outputs")
    items = wave_report_input.get("items")
    events = wave_report_input.get("events")
    source_refs = wave_report_input.get("source_refs")
    proof_pack_posture = wave_report_input.get("proof_pack_posture")
    forbidden_actions = (
        supportability.get("forbidden_actions") if isinstance(supportability, dict) else []
    )

    wave_id = _as_str(wave_report_input.get("wave_id"))
    wave_state = _as_str(wave_report_input.get("wave_state"))
    content_hash = _as_str(wave_report_input.get("content_hash"))
    wave_content_hash = _as_str(wave_report_input.get("wave_content_hash"))
    item_count = len(items) if isinstance(items, list) else 0
    event_count = len(events) if isinstance(events, list) else 0
    source_ref_count = len(source_refs) if isinstance(source_refs, list) else 0
    proof_pack_ref_count = _proof_pack_ref_count(proof_pack_posture)
    output_count = len(requested_outputs) if isinstance(requested_outputs, list) else 0
    portfolio_memory_summary = portfolio_memory_context_summary(context_payload)

    message = (
        "Drafted a review-gated DPM rebalance-wave PM memo from bounded manage wave evidence "
        f"for wave {wave_id} in state {wave_state}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": "dpm_wave_pm_memo",
        "narrative_type": "rebalance_wave_pm_memo",
        "state": "REVIEW_REQUIRED",
        "scope": "support_only",
        "wave_id": wave_id,
        "wave_state": wave_state,
        "wave_content_hash": wave_content_hash,
        "wave_report_content_hash": content_hash,
        "requested_outputs": requested_outputs if isinstance(requested_outputs, list) else [],
        "item_count": item_count,
        "event_count": event_count,
        "source_ref_count": source_ref_count,
        "proof_pack_ref_count": proof_pack_ref_count,
        "output_count": output_count,
        "forbidden_actions": forbidden_actions if isinstance(forbidden_actions, list) else [],
        **portfolio_memory_summary,
        "unsupported_claims": _unsupported_claims(supportability),
        "review_guidance": [
            "Review the memo against the source wave report hash before using it in PM workflow.",
            "Do not treat this memo as wave approval, trade approval, client communication, or order instruction.",
            "Escalate missing wave, proof-pack, or source evidence instead of asking the model to infer it.",
            "Use portfolio memory only as bounded source lineage; do not reconstruct missing facts.",
        ],
    }
    return message, structured_output


def _proof_pack_ref_count(proof_pack_posture: object) -> int:
    if not isinstance(proof_pack_posture, dict):
        return 0
    refs = proof_pack_posture.get("proof_pack_refs")
    if isinstance(refs, list):
        return len(refs)
    count = proof_pack_posture.get("proof_pack_count")
    return count if isinstance(count, int) else 0


def _unsupported_claims(supportability: object) -> list[str]:
    if not isinstance(supportability, dict):
        return []
    value = supportability.get("unsupported_claims")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""
