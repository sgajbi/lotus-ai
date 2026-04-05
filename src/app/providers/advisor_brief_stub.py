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
    portfolio_label = _safe_str(portfolio.get("display_label")) or portfolio_id
    period_label = _safe_str(period.get("period")) or "the selected period"
    portfolio_return = _format_pct(performance.get("portfolio_return_pct"))
    benchmark_return = _format_pct(performance.get("benchmark_return_pct"))
    active_return = _format_pct(performance.get("active_return_pct"))
    net_flow = _format_currency(performance.get("net_cash_flow"))
    end_market_value = _format_currency(performance.get("end_market_value"))
    money_weighted_return = _format_pct(performance.get("money_weighted_return_pct"))
    top_contributor = _pick_position(contribution.get("top_positions"))
    top_detractor = _pick_position(contribution.get("bottom_positions"))
    top_effect = _pick_effect(attribution.get("top_effects"))
    coverage_state = _derive_coverage_state(supportability)
    summary_ref = source_refs[0] if source_refs else None
    detail_ref = source_refs[1] if len(source_refs) > 1 else summary_ref

    if not source_refs or (
        portfolio_return == "N/A" and benchmark_return == "N/A" and active_return == "N/A"
    ):
        message = (
            "Advisor brief unavailable: source performance facts or source references are "
            "insufficient for a grounded explanation."
        )
        return message, {
            "advisor_brief_status": "unavailable",
            "coverage_state": coverage_state,
            "portfolio_id": portfolio_id,
            "period": period_label,
            "source_refs": source_refs,
            "grounded_summary": message,
            "grounded_facts": [],
            "talking_points": [],
            "recommended_actions": [],
            "risks_and_exceptions": [
                {
                    "headline": "Advisor Brief is unavailable.",
                    "detail": (
                        "No client-ready narrative was generated because the supplied "
                        "performance facts or source references were insufficient."
                    ),
                    "tone": "warning",
                    "evidence_refs": [],
                }
            ],
        }

    summary_parts = [
        (
            f"{portfolio_label} delivered {portfolio_return} over {period_label} versus "
            f"{benchmark_return} for the benchmark, resulting in {active_return} active return"
        ),
        f"net flow was {net_flow} and ending market value was {end_market_value}",
    ]
    if top_contributor and top_detractor:
        summary_parts.append(
            f"largest contribution came from {top_contributor['label']} "
            f"({top_contributor['contribution']}) while the main drag was "
            f"{top_detractor['label']} ({top_detractor['contribution']})"
        )
    elif top_contributor:
        summary_parts.append(
            f"largest contribution came from {top_contributor['label']} "
            f"({top_contributor['contribution']})"
        )
    if top_effect:
        summary_parts.append(
            f"largest benchmark-relative attribution effect was {top_effect['label']} "
            f"({top_effect['effect']})"
        )

    message = ". ".join(summary_parts) + "."
    return message, {
        "advisor_brief_status": coverage_state,
        "coverage_state": coverage_state,
        "portfolio_id": portfolio_id,
        "period": period_label,
        "source_refs": source_refs,
        "grounded_summary": message,
        "talking_points": _build_talking_points(
            period_label=period_label,
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            active_return=active_return,
            top_contributor=top_contributor,
            top_detractor=top_detractor,
            top_effect=top_effect,
            summary_ref=summary_ref,
            detail_ref=detail_ref,
        ),
        "recommended_actions": _build_recommended_actions(
            top_detractor=top_detractor,
            top_effect=top_effect,
            detail_ref=detail_ref,
        ),
        "risks_and_exceptions": _build_risks_and_exceptions(
            coverage_state=coverage_state,
            supportability=supportability,
            detail_ref=detail_ref,
        ),
        "grounded_facts": [
            {
                "metric_label": "Portfolio Return",
                "metric_value": portfolio_return,
                "source_ref": summary_ref,
            },
            {
                "metric_label": "Benchmark Return",
                "metric_value": benchmark_return,
                "source_ref": summary_ref,
            },
            {
                "metric_label": "Active Return",
                "metric_value": active_return,
                "source_ref": summary_ref,
            },
            {
                "metric_label": "Money-Weighted Return",
                "metric_value": money_weighted_return,
                "source_ref": summary_ref,
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


def _build_talking_points(
    *,
    period_label: str,
    portfolio_return: str,
    benchmark_return: str,
    active_return: str,
    top_contributor: dict[str, str] | None,
    top_detractor: dict[str, str] | None,
    top_effect: dict[str, str] | None,
    summary_ref: str | None,
    detail_ref: str | None,
) -> list[dict[str, Any]]:
    points = [
        {
            "headline": f"{period_label} active return was {active_return}.",
            "detail": (
                f"Portfolio Return was {portfolio_return} versus Benchmark Return "
                f"{benchmark_return}. Review Return Path for period-by-period context."
            ),
            "tone": "warning" if active_return.startswith("-") else "positive",
            "evidence_refs": [
                {
                    "metric_label": "Active Return",
                    "metric_value": active_return,
                    "source_ref": summary_ref,
                }
            ],
        }
    ]

    if top_contributor:
        detail = (
            f"{top_contributor['label']} contributed {top_contributor['contribution']} "
            f"with return {top_contributor['return']}."
        )
        if top_detractor:
            detail += (
                f" Main drag came from {top_detractor['label']} at "
                f"{top_detractor['contribution']}."
            )
        points.append(
            {
                "headline": f"Largest contribution came from {top_contributor['label']}.",
                "detail": detail,
                "tone": "positive",
                "evidence_refs": [
                    {
                        "metric_label": "Top Contributor",
                        "metric_value": top_contributor["contribution"],
                        "source_ref": detail_ref,
                    }
                ],
            }
        )

    if top_effect:
        points.append(
            {
                "headline": (
                    f"Largest benchmark-relative attribution effect was "
                    f"{top_effect['label']}."
                ),
                "detail": (
                    f"Total Effect was {top_effect['effect']}. Use Attribution Detail to "
                    "review Allocation, Selection, and Interaction."
                ),
                "tone": "warning" if top_effect["effect"].startswith("-") else "neutral",
                "evidence_refs": [
                    {
                        "metric_label": "Top Effect",
                        "metric_value": top_effect["effect"],
                        "source_ref": detail_ref,
                    }
                ],
            }
        )
    return points


def _build_recommended_actions(
    *,
    top_detractor: dict[str, str] | None,
    top_effect: dict[str, str] | None,
    detail_ref: str | None,
) -> list[dict[str, Any]]:
    actions = [
        {
            "label": "Review Return Path",
            "detail": "Explain the benchmark gap with period-level return and flow context.",
            "evidence_refs": [
                {
                    "metric_label": "Advisor Brief",
                    "metric_value": "Source-Grounded",
                    "source_ref": detail_ref,
                }
            ],
        }
    ]
    if top_detractor:
        actions.append(
            {
                "label": f"Investigate {top_detractor['label']}",
                "detail": (
                    f"Validate whether the {top_detractor['contribution']} drag is expected, "
                    "cash-related, or a positioning issue before the client conversation."
                ),
                "evidence_refs": [
                    {
                        "metric_label": "Top Detractor",
                        "metric_value": top_detractor["contribution"],
                        "source_ref": detail_ref,
                    }
                ],
            }
        )
    if top_effect:
        actions.append(
            {
                "label": "Review Attribution Drivers",
                "detail": (
                    f"Use {top_effect['label']} to anchor the benchmark-relative explanation "
                    "and confirm whether the effect is allocation- or selection-led."
                ),
                "evidence_refs": [
                    {
                        "metric_label": "Top Effect",
                        "metric_value": top_effect["effect"],
                        "source_ref": detail_ref,
                    }
                ],
            }
        )
    return actions


def _build_risks_and_exceptions(
    *,
    coverage_state: str,
    supportability: list[Any],
    detail_ref: str | None,
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for item in supportability:
        support_item = _safe_dict(item)
        value = _safe_str(support_item.get("value")) or ""
        if value.lower() not in {"partial", "unavailable"}:
            continue
        label = _safe_str(support_item.get("label")) or _safe_str(support_item.get("key"))
        if not label:
            continue
        risks.append(
            {
                "headline": f"{label} is {value.lower()}.",
                "detail": (
                    "Keep the client explanation constrained to available source metrics and "
                    "verify unsupported analytics directly in Workbench."
                ),
                "tone": "warning",
                "evidence_refs": [
                    {
                        "metric_label": label,
                        "metric_value": value.title(),
                        "source_ref": detail_ref,
                    }
                ],
            }
        )
    if coverage_state == "ready" and not risks:
        risks.append(
            {
                "headline": "No material supportability exception is flagged in the supplied facts.",
                "detail": (
                    "Cross-check the final client narrative against Return Path, Contribution, "
                    "and Attribution before external use."
                ),
                "tone": "neutral",
                "evidence_refs": [
                    {
                        "metric_label": "Advisor Brief",
                        "metric_value": "Ready",
                        "source_ref": detail_ref,
                    }
                ],
            }
        )
    return risks


def _pick_position(value: Any) -> dict[str, str] | None:
    rows = _safe_list(value)
    if not rows:
        return None
    row = _safe_dict(rows[0])
    label = _safe_str(row.get("display_label")) or _normalize_position_label(
        _safe_str(row.get("position_id"))
    )
    if not label:
        return None
    return {
        "label": label,
        "contribution": _format_pct(
            row.get("contribution_pct", row.get("total_contribution_pct"))
        ),
        "return": _format_pct(row.get("total_return_pct")),
    }


def _pick_effect(value: Any) -> dict[str, str] | None:
    rows = _safe_list(value)
    if not rows:
        return None
    row = _safe_dict(rows[0])
    label = _safe_str(row.get("key_label"))
    if not label:
        return None
    return {
        "label": label,
        "effect": _format_pct(row.get("total_effect_pct")),
    }


def _format_pct(value: Any) -> str:
    if not isinstance(value, int | float):
        return "N/A"
    return f"{float(value):.2f}%"


def _format_currency(value: Any) -> str:
    if not isinstance(value, int | float):
        return "N/A"
    return f"${float(value):,.0f}"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_position_label(position_id: str | None) -> str | None:
    if not position_id:
        return None
    raw_label = position_id.rsplit(":", 1)[-1].strip()
    known_prefixes = ("FO_EQ_", "FO_FI_", "FO_CASH_", "FO_ALT_", "FO_FX_")
    for prefix in known_prefixes:
        if raw_label.startswith(prefix):
            raw_label = raw_label[len(prefix):]
            break
    return raw_label.replace("_", " ").strip() or None
