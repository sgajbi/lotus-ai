from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from app.providers.advisor_brief_stub import build_advisor_brief_stub_result

_FORBIDDEN_SUMMARY_FRAGMENTS = (
    "output contract",
    "return json only",
    "structured lotus domain",
    "provided data and context",
    "caller_app",
    "context_payload",
    "source_refs",
    "advisor brief output contract",
    "task_id",
)
_PERCENT_TOKEN_PATTERN = re.compile(r"(?<![\w-])[-+]?\d+(?:\.\d+)?%")
_CURRENCY_TOKEN_PATTERN = re.compile(r"(?<![\w-])[-+]?\$\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class AdvisorBriefQualityResult:
    message: str
    structured_output: dict[str, Any]
    guardrail_triggered: bool
    guardrail_reason: str | None


def build_advisor_brief_user_message(
    *,
    task_id: str,
    caller_app: str,
    context_summary: str,
    context_payload: dict[str, Any],
    source_refs: list[str],
) -> str:
    import json

    contract = (
        "Return JSON only with keys grounded_summary, talking_points, "
        "recommended_actions, and risks_and_exceptions. Return at most 3 talking points, "
        "3 recommended actions, and 3 risks/exceptions. Keep grounded_summary under 450 "
        "characters and each detail under 220 characters. Each talking point and risk item "
        "must include headline, detail, tone, and evidence_refs. Use tone values positive, "
        "neutral, or warning only. Each evidence ref must use metric_label, metric_value, "
        "and source_ref from the supplied source_refs only. Each recommended action must "
        "include label, detail, and evidence_refs. Prefer portfolio.display_label, "
        "benchmark.benchmark_name, and position display_label fields when present. Never "
        "show raw portfolio_id, benchmark_code, or position_id identifiers if a display "
        "label is available. Do not invent facts that are absent from context_payload."
    )
    sections = [
        "Produce a bounded advisor brief for a private-banking workstation.",
        contract,
        f"Task: {task_id}",
        f"Caller: {caller_app}",
        f"Context Summary:\n{context_summary}",
        f"Source Refs:\n{json.dumps(source_refs, indent=2)}",
        f"Context Payload:\n{json.dumps(context_payload, indent=2, sort_keys=True)}",
    ]
    return "\n\n".join(sections)


def normalize_advisor_brief_output(
    *,
    parsed_output: dict[str, Any] | None,
    output_message: str,
    context_payload: dict[str, Any],
    source_refs: list[str],
) -> AdvisorBriefQualityResult:
    fallback_message, fallback_output = _build_fallback_result(
        context_payload=context_payload,
        source_refs=source_refs,
    )

    if parsed_output is None:
        extracted_summary = extract_grounded_summary_fragment(output_message)
        if extracted_summary and not _contains_forbidden_summary_language(extracted_summary):
            return AdvisorBriefQualityResult(
                message=extracted_summary,
                structured_output={
                    "grounded_summary": extracted_summary,
                    "talking_points": [],
                    "recommended_actions": [],
                    "risks_and_exceptions": [],
                    "advisor_brief_guardrail_triggered": False,
                    "advisor_brief_guardrail_reason": None,
                    "raw_output_excerpt": _build_output_excerpt(output_message),
                },
                guardrail_triggered=False,
                guardrail_reason=None,
            )
        return _fallback_result(
            message=fallback_message,
            output=fallback_output,
            reason="missing_valid_json",
        )

    grounded_summary = _clean_text(parsed_output.get("grounded_summary"))
    talking_points = _normalize_narrative_items(parsed_output.get("talking_points"))
    recommended_actions = _normalize_action_items(parsed_output.get("recommended_actions"))
    risks_and_exceptions = _normalize_narrative_items(
        parsed_output.get("risks_and_exceptions")
    )

    if not grounded_summary:
        return _fallback_result(
            message=fallback_message,
            output=fallback_output,
            reason="missing_grounded_summary",
        )

    if _contains_forbidden_summary_language(grounded_summary):
        return _fallback_result(
            message=fallback_message,
            output=fallback_output,
            reason="invalid_grounded_summary_language",
        )

    if _has_numeric_consistency_mismatch(
        grounded_summary=grounded_summary,
        context_payload=context_payload,
    ):
        return _fallback_result(
            message=fallback_message,
            output=fallback_output,
            reason="numeric_consistency_mismatch",
        )

    return AdvisorBriefQualityResult(
        message=grounded_summary,
        structured_output={
            "grounded_summary": grounded_summary,
            "talking_points": talking_points,
            "recommended_actions": recommended_actions,
            "risks_and_exceptions": risks_and_exceptions,
            "advisor_brief_guardrail_triggered": False,
            "advisor_brief_guardrail_reason": None,
            "raw_output_excerpt": _build_output_excerpt(output_message),
        },
        guardrail_triggered=False,
        guardrail_reason=None,
    )


def _build_fallback_result(
    *,
    context_payload: dict[str, Any],
    source_refs: list[str],
) -> tuple[str, dict[str, Any]]:
    result = build_advisor_brief_stub_result(
        context_payload=context_payload,
        source_refs=source_refs,
    )
    if result is None:
        message = (
            "Advisor brief unavailable: source performance facts or source references are "
            "insufficient for a grounded explanation."
        )
        return message, {
            "grounded_summary": message,
            "talking_points": [],
            "recommended_actions": [],
            "risks_and_exceptions": [],
        }
    return result


def _fallback_result(
    *,
    message: str,
    output: dict[str, Any],
    reason: str,
) -> AdvisorBriefQualityResult:
    normalized_output = dict(output)
    normalized_output["advisor_brief_guardrail_triggered"] = True
    normalized_output["advisor_brief_guardrail_reason"] = reason
    return AdvisorBriefQualityResult(
        message=message,
        structured_output=normalized_output,
        guardrail_triggered=True,
        guardrail_reason=reason,
    )


def _normalize_narrative_items(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    items: list[dict[str, Any]] = []
    for row in rows[:3]:
        item = row if isinstance(row, dict) else {}
        headline = _clean_text(item.get("headline"))
        detail = _clean_text(item.get("detail"))
        tone = _clean_text(item.get("tone")) or "neutral"
        if not headline or not detail:
            continue
        if _contains_forbidden_summary_language(headline) or _contains_forbidden_summary_language(
            detail
        ):
            continue
        if tone not in {"positive", "neutral", "warning"}:
            tone = "neutral"
        items.append(
            {
                "headline": headline,
                "detail": detail,
                "tone": tone,
                "evidence_refs": _normalize_evidence_refs(item.get("evidence_refs")),
            }
        )
    return items


def _normalize_action_items(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    items: list[dict[str, Any]] = []
    for row in rows[:3]:
        item = row if isinstance(row, dict) else {}
        label = _clean_text(item.get("label"))
        detail = _clean_text(item.get("detail"))
        if not label:
            continue
        if _contains_forbidden_summary_language(label) or (
            detail and _contains_forbidden_summary_language(detail)
        ):
            continue
        items.append(
            {
                "label": label,
                "detail": detail or "",
                "evidence_refs": _normalize_evidence_refs(item.get("evidence_refs")),
            }
        )
    return items


def _normalize_evidence_refs(value: Any) -> list[dict[str, str]]:
    rows = value if isinstance(value, list) else []
    items: list[dict[str, str]] = []
    for row in rows:
        item = row if isinstance(row, dict) else {}
        metric_label = _clean_text(item.get("metric_label"))
        metric_value = _clean_text(item.get("metric_value"))
        source_ref = _clean_text(item.get("source_ref"))
        if not metric_label or not metric_value or not source_ref:
            continue
        items.append(
            {
                "metric_label": metric_label,
                "metric_value": metric_value,
                "source_ref": source_ref,
            }
        )
    return items


def _contains_forbidden_summary_language(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    if normalized.startswith("{") or normalized.startswith("```") or "```" in normalized:
        return True
    return any(fragment in normalized for fragment in _FORBIDDEN_SUMMARY_FRAGMENTS)


def _has_numeric_consistency_mismatch(
    *,
    grounded_summary: str,
    context_payload: dict[str, Any],
) -> bool:
    performance = context_payload.get("performance")
    if not isinstance(performance, dict):
        return False
    allowed_percents = [
        float(value)
        for value in (
            performance.get("portfolio_return_pct"),
            performance.get("benchmark_return_pct"),
            performance.get("active_return_pct"),
            performance.get("money_weighted_return_pct"),
        )
        if isinstance(value, int | float)
    ]
    allowed_currency_values = [
        float(value)
        for value in (
            performance.get("net_cash_flow"),
            performance.get("end_market_value"),
        )
        if isinstance(value, int | float)
    ]

    for token in _PERCENT_TOKEN_PATTERN.findall(grounded_summary):
        try:
            candidate = float(token.replace("%", "").replace(",", ""))
        except ValueError:
            continue
        if not any(abs(candidate - expected) <= 0.02 for expected in allowed_percents):
            return True

    for token in _CURRENCY_TOKEN_PATTERN.findall(grounded_summary):
        normalized = token.replace("$", "").replace(",", "")
        if not normalized:
            continue
        try:
            candidate = float(normalized)
        except ValueError:
            continue
        if not any(abs(candidate - expected) <= 1.0 for expected in allowed_currency_values):
            return True

    return False


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized if normalized else None


def _build_output_excerpt(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= 280:
        return normalized
    return normalized[:277] + "..."


def extract_grounded_summary_fragment(value: str) -> str | None:
    match = re.search(r'"grounded_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', value, flags=re.S)
    if match is None:
        return None
    try:
        parsed = json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, str) and parsed.strip() else None
