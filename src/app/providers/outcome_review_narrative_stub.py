from __future__ import annotations

from typing import Any


def build_outcome_review_narrative_stub_result(
    *,
    context_payload: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    ai_evidence = context_payload.get("ai_evidence_input")
    narrative_request = context_payload.get("narrative_request")
    if not isinstance(ai_evidence, dict) or not isinstance(narrative_request, dict):
        return None

    outcome_review_id = str(ai_evidence.get("outcome_review_id", "unknown"))
    portfolio_id = str(ai_evidence.get("portfolio_id", "unknown"))
    dimensions = ai_evidence.get("dimensions")
    source_refs = ai_evidence.get("source_refs")
    requested_outputs = narrative_request.get("requested_outputs")
    dimension_count = len(dimensions) if isinstance(dimensions, list) else 0
    source_ref_count = len(source_refs) if isinstance(source_refs, list) else 0
    output_sections = (
        sorted(str(item) for item in requested_outputs)
        if isinstance(requested_outputs, list)
        else []
    )

    message = (
        f"Outcome review {outcome_review_id} for portfolio {portfolio_id} is ready for "
        "review-gated narrative support from bounded outcome evidence."
    )
    structured_output = {
        "outcome_review_narrative_status": "REVIEW_REQUIRED",
        "narrative_scope": "support_only",
        "portfolio_id": portfolio_id,
        "outcome_review_id": outcome_review_id,
        "evidence_content_hash": ai_evidence.get("content_hash"),
        "outcome_review_content_hash": ai_evidence.get("outcome_review_content_hash"),
        "overall_outcome": ai_evidence.get("overall_outcome"),
        "requested_outputs": output_sections,
        "dimension_count": dimension_count,
        "source_ref_count": source_ref_count,
        "forbidden_actions_enforced": sorted(ai_evidence.get("forbidden_actions", [])),
        "forbidden_fields_removed": sorted(ai_evidence.get("forbidden_fields_removed", [])),
        "unsupported_claims": [
            "client_contact",
            "trade_approval",
            "portfolio_manager_scoring",
            "source_fact_invention",
        ],
        "review_guidance": (
            "Use this generated posture as PM/CIO support only. Business approval, client contact, "
            "execution instructions, and source-data correction remain outside lotus-ai authority."
        ),
    }
    return message, structured_output
