from __future__ import annotations

from typing import Any

from app.services.portfolio_memory_context_guardrails import portfolio_memory_context_summary


def build_pm_quality_summary_stub_result(
    *,
    context_payload: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    score_run = context_payload.get("score_run")
    summary_request = context_payload.get("summary_request")
    supportability = context_payload.get("supportability")
    if (
        not isinstance(score_run, dict)
        or not isinstance(summary_request, dict)
        or not isinstance(supportability, dict)
    ):
        return None

    score_run_id = str(score_run.get("score_run_id", "unknown"))
    portfolio_manager_id = str(score_run.get("portfolio_manager_id", "unknown"))
    indicator_results = score_run.get("indicator_results")
    source_refs = score_run.get("source_refs")
    requested_outputs = summary_request.get("requested_outputs")
    output_sections = (
        sorted(str(item) for item in requested_outputs)
        if isinstance(requested_outputs, list)
        else []
    )
    portfolio_memory_summary = portfolio_memory_context_summary(context_payload)

    message = (
        f"PM quality score run {score_run_id} for portfolio manager {portfolio_manager_id} "
        "is ready for review-gated support-only summary from Manage-owned score-run evidence."
    )
    structured_output = {
        "workflow_pack_family": "pm_quality_summary",
        "narrative_type": "pm_quality_summary",
        "state": "REVIEW_REQUIRED",
        "scope": "support_only",
        "score_run_id": score_run_id,
        "policy_id": score_run.get("policy_id"),
        "policy_version": score_run.get("policy_version"),
        "portfolio_manager_id": portfolio_manager_id,
        "portfolio_id": score_run.get("portfolio_id"),
        "score_run_state": score_run.get("state"),
        "score_run_content_hash": score_run.get("content_hash"),
        "reason_codes": sorted(score_run.get("reason_codes", [])),
        "indicator_result_count": (
            len(indicator_results) if isinstance(indicator_results, list) else 0
        ),
        "source_ref_count": len(source_refs) if isinstance(source_refs, list) else 0,
        "requested_outputs": output_sections,
        "forbidden_actions_enforced": sorted(supportability.get("forbidden_actions", [])),
        **portfolio_memory_summary,
        "unsupported_claims": [
            "pm_ranking",
            "hr_decision",
            "compensation_decision",
            "conduct_enforcement",
            "client_contact",
            "trade_approval",
            "execution_instruction",
            "score_calculation",
            "source_fact_invention",
        ],
        "review_guidance": (
            "Use this generated posture as PM operating-quality support only. Manage owns the "
            "score-run evidence; lotus-ai does not calculate scores, rank PMs, approve trades, "
            "contact clients, or create HR, compensation, conduct, execution, or OMS decisions."
        ),
    }
    return message, structured_output
