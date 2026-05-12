from __future__ import annotations

from typing import Any

from app.services.portfolio_memory_context_guardrails import portfolio_memory_context_summary


def build_dpm_exception_summary_stub_result(
    *,
    context_payload: dict[str, object],
) -> tuple[str, dict[str, object]] | None:
    exception_input = context_payload.get("exception_summary_input")
    summary_request = context_payload.get("exception_summary_request")
    supportability = context_payload.get("supportability")
    if not isinstance(exception_input, dict) or not isinstance(summary_request, dict):
        return None

    exceptions = exception_input.get("exceptions")
    requested_outputs = summary_request.get("requested_outputs")
    portfolio_id = _as_str(exception_input.get("portfolio_id"))
    mandate_id = _as_str(exception_input.get("mandate_id"))
    content_hash = _as_str(exception_input.get("content_hash"))
    exception_count = len(exceptions) if isinstance(exceptions, list) else 0
    open_exception_count = _count_by_state(exceptions, "OPEN")
    critical_exception_count = _count_by_severity(exceptions, "CRITICAL")
    high_exception_count = _count_by_severity(exceptions, "HIGH")
    portfolio_memory_summary = portfolio_memory_context_summary(context_payload)

    message = (
        "Drafted a review-gated DPM exception summary from bounded manage monitoring "
        f"exception evidence for portfolio {portfolio_id}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": "dpm_exception_summary",
        "narrative_type": "dpm_exception_summary",
        "state": "REVIEW_REQUIRED",
        "scope": "support_only",
        "portfolio_id": portfolio_id,
        "mandate_id": mandate_id,
        "exception_summary_content_hash": content_hash,
        "requested_outputs": requested_outputs if isinstance(requested_outputs, list) else [],
        "exception_count": exception_count,
        "open_exception_count": open_exception_count,
        "critical_exception_count": critical_exception_count,
        "high_exception_count": high_exception_count,
        **portfolio_memory_summary,
        "unsupported_claims": _unsupported_claims(supportability),
        "review_guidance": [
            "Review the summary against the source exception evidence hash before operational use.",
            "Do not treat this summary as PM scoring, approval, client communication, or order instruction.",
            "Escalate missing source refs or stale exception posture instead of inferring status.",
            "Use portfolio memory only as bounded lineage; do not reconstruct missing facts.",
        ],
    }
    return message, structured_output


def _count_by_state(exceptions: object, state: str) -> int:
    if not isinstance(exceptions, list):
        return 0
    return sum(
        1
        for item in exceptions
        if isinstance(item, dict) and isinstance(item.get("state"), str) and item["state"] == state
    )


def _count_by_severity(exceptions: object, severity: str) -> int:
    if not isinstance(exceptions, list):
        return 0
    return sum(
        1
        for item in exceptions
        if isinstance(item, dict)
        and isinstance(item.get("severity"), str)
        and item["severity"] == severity
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
