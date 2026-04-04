from __future__ import annotations

from typing import Any


def build_advisor_brief_stub_result(
    *,
    context_payload: dict[str, Any],
    source_refs: list[str],
) -> tuple[str, dict[str, Any]] | None:
    if not _is_advisor_brief_payload(context_payload):
        return None

    portfolio = _safe_dict(context_payload.get("portfolio"))
    period = _safe_dict(context_payload.get("period"))
    performance = _safe_dict(context_payload.get("performance"))
    supportability = _safe_list(context_payload.get("supportability"))
    contribution = _safe_dict(context_payload.get("contribution"))
    attribution = _safe_dict(context_payload.get("attribution"))

    portfolio_id = _safe_str(portfolio.get("portfolio_id")) or "the selected portfolio"
    period_label = _safe_str(period.get("period")) or "the selected period"
    portfolio_return = _format_pct(performance.get("portfolio_return_pct"))
    benchmark_return = _format_pct(performance.get("benchmark_return_pct"))
    active_return = _format_pct(performance.get("active_return_pct"))
    top_contributor = _pick_position_name(contribution.get("top_positions"))
    top_effect = _pick_effect_name(attribution.get("top_effects"))

    if not source_refs or (
        portfolio_return == "N/A" and benchmark_return == "N/A" and active_return == "N/A"
    ):
        message = (
            "Advisor brief unavailable: source performance facts or source references are "
            "insufficient for a grounded explanation."
        )
        return message, {
            "advisor_brief_status": "unavailable",
            "coverage_state": _derive_coverage_state(supportability),
            "portfolio_id": portfolio_id,
            "period": period_label,
            "source_refs": source_refs,
            "grounded_summary": message,
            "grounded_facts": [],
        }

    summary_parts = [
        f"{period_label} portfolio return is {portfolio_return}",
        f"benchmark return is {benchmark_return}",
        f"active return is {active_return}",
    ]
    if top_contributor:
        summary_parts.append(f"top contributor is {top_contributor}")
    if top_effect:
        summary_parts.append(f"largest attribution effect is {top_effect}")

    message = f"Advisor brief for {portfolio_id}: " + "; ".join(summary_parts) + "."
    return message, {
        "advisor_brief_status": _derive_coverage_state(supportability),
        "coverage_state": _derive_coverage_state(supportability),
        "portfolio_id": portfolio_id,
        "period": period_label,
        "source_refs": source_refs,
        "grounded_summary": message,
        "grounded_facts": [
            {
                "metric_label": "Portfolio Return",
                "metric_value": portfolio_return,
                "source_ref": source_refs[0],
            },
            {
                "metric_label": "Benchmark Return",
                "metric_value": benchmark_return,
                "source_ref": source_refs[0],
            },
            {
                "metric_label": "Active Return",
                "metric_value": active_return,
                "source_ref": source_refs[0],
            },
        ],
    }


def _is_advisor_brief_payload(payload: dict[str, Any]) -> bool:
    return {"portfolio", "period", "performance", "supportability"}.issubset(payload.keys())


def _derive_coverage_state(supportability: list[Any]) -> str:
    states = {
        str(item.get("value", "")).lower()
        for item in supportability
        if isinstance(item, dict)
    }
    if "unavailable" in states:
        return "partial"
    if "partial" in states:
        return "partial"
    return "ready"


def _pick_position_name(value: Any) -> str | None:
    rows = _safe_list(value)
    if not rows:
        return None
    return _safe_str(_safe_dict(rows[0]).get("position_id"))


def _pick_effect_name(value: Any) -> str | None:
    rows = _safe_list(value)
    if not rows:
        return None
    return _safe_str(_safe_dict(rows[0]).get("key_label"))


def _format_pct(value: Any) -> str:
    if not isinstance(value, int | float):
        return "N/A"
    return f"{float(value):.2f}%"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
