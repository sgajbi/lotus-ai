from app.providers.advisor_brief_quality_guardrails import (
    build_advisor_brief_user_message,
    extract_grounded_summary_fragment,
    normalize_advisor_brief_output,
)


def _advisor_context() -> dict[str, object]:
    return {
        "portfolio": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "display_label": "PB SG GLOBAL BAL 001",
        },
        "period": {"period": "YTD"},
        "benchmark": {"benchmark_name": "Private Banking Global Balanced 60/40"},
        "performance": {
            "portfolio_return_pct": 1.25,
            "benchmark_return_pct": 7.93,
            "active_return_pct": -6.68,
            "net_cash_flow": 14725.0,
            "end_market_value": 1087461.0,
        },
        "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
        "contribution": {
            "top_positions": [
                {
                    "position_id": "PB_SG_GLOBAL_BAL_001:FO_EQ_AAPL_US",
                    "display_label": "AAPL US",
                    "contribution_pct": 0.29551,
                    "total_return_pct": 4.31,
                }
            ]
        },
        "attribution": {"top_effects": []},
    }


def test_build_advisor_brief_user_message_uses_bounded_sections() -> None:
    message = build_advisor_brief_user_message(
        task_id="explain.v1",
        caller_app="lotus-gateway",
        context_summary="Generate advisor brief.",
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    assert "Return JSON only with keys grounded_summary" in message
    assert "Context Payload:" in message
    assert "output_contract_override" not in message
    assert '"display_label": "PB SG GLOBAL BAL 001"' in message


def test_normalize_advisor_brief_output_falls_back_when_summary_leaks_contract_text() -> None:
    result = normalize_advisor_brief_output(
        parsed_output={
            "grounded_summary": (
                "The output contract for the structured Lotus domain with the provided data "
                "and context is as follows."
            ),
            "talking_points": [],
            "recommended_actions": [],
            "risks_and_exceptions": [],
        },
        output_message="bad local output",
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    assert result.guardrail_triggered is True
    assert result.guardrail_reason == "invalid_grounded_summary_language"
    assert "PB SG GLOBAL BAL 001 delivered 1.25% over YTD" in result.message
    assert result.structured_output["advisor_brief_guardrail_triggered"] is True
    assert result.structured_output["talking_points"]


def test_normalize_advisor_brief_output_falls_back_on_numeric_consistency_mismatch() -> None:
    result = normalize_advisor_brief_output(
        parsed_output={
            "grounded_summary": (
                "The portfolio PB SG GLOBAL BAL 001 shows a net return of 6.80898% in the "
                "YTD period, reflecting a performance gap."
            ),
            "talking_points": [{"headline": "Active return lagged.", "detail": "Review YTD gap."}],
            "recommended_actions": [],
            "risks_and_exceptions": [],
        },
        output_message="bad numeric summary",
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    assert result.guardrail_triggered is True
    assert result.guardrail_reason == "numeric_consistency_mismatch"
    assert "PB SG GLOBAL BAL 001 delivered 1.25% over YTD" in result.message


def test_normalize_advisor_brief_output_preserves_clean_structured_brief() -> None:
    result = normalize_advisor_brief_output(
        parsed_output={
            "grounded_summary": "Portfolio lagged benchmark on YTD because equity exposure trailed.",
            "talking_points": [
                {
                    "headline": "Active return was negative.",
                    "detail": "Portfolio return was 1.25% versus benchmark 7.93%.",
                    "tone": "warning",
                    "evidence_refs": [
                        {
                            "metric_label": "Active Return",
                            "metric_value": "-6.68%",
                            "source_ref": "lotus-gateway:workbench:performance-summary:YTD",
                        }
                    ],
                }
            ],
            "recommended_actions": [
                {
                    "label": "Review Attribution Drivers",
                    "detail": "Open Attribution Detail before the client discussion.",
                    "evidence_refs": [],
                }
            ],
            "risks_and_exceptions": [],
        },
        output_message="ignored once structured output is valid",
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    assert result.guardrail_triggered is False
    assert result.message == "Portfolio lagged benchmark on YTD because equity exposure trailed."
    assert (
        result.structured_output["talking_points"][0]["headline"] == "Active return was negative."
    )
    assert result.structured_output["recommended_actions"][0]["label"] == (
        "Review Attribution Drivers"
    )


def test_normalize_advisor_brief_output_uses_extracted_summary_when_json_is_truncated() -> None:
    result = normalize_advisor_brief_output(
        parsed_output=None,
        output_message=(
            '{"grounded_summary":"Portfolio lagged benchmark on YTD.",'
            '"talking_points":[{"headline":"broken"'
        ),
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    assert result.guardrail_triggered is False
    assert result.message == "Portfolio lagged benchmark on YTD."
    assert result.structured_output["raw_output_excerpt"].startswith('{"grounded_summary"')


def test_normalize_advisor_brief_output_falls_back_when_truncated_summary_leaks_contract_text() -> None:
    result = normalize_advisor_brief_output(
        parsed_output=None,
        output_message=(
            '{"grounded_summary":"Return JSON only with keys grounded_summary and talking_points."'
        ),
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    assert result.guardrail_triggered is True
    assert result.guardrail_reason == "missing_valid_json"
    assert "PB SG GLOBAL BAL 001 delivered 1.25% over YTD" in result.message


def test_normalize_advisor_brief_output_sanitizes_invalid_items_and_tones() -> None:
    result = normalize_advisor_brief_output(
        parsed_output={
            "grounded_summary": "Portfolio lagged benchmark on YTD because equity exposure trailed.",
            "talking_points": [
                {
                    "headline": "Keep",
                    "detail": "Valid item.",
                    "tone": "severe",
                    "evidence_refs": [
                        {
                            "metric_label": "Active Return",
                            "metric_value": "-6.68%",
                            "source_ref": "lotus-gateway:workbench:performance-summary:YTD",
                        },
                        {"metric_label": "Incomplete", "metric_value": "-6.68%"},
                    ],
                },
                {
                    "headline": "Return JSON only with keys grounded_summary",
                    "detail": "Should be discarded.",
                    "tone": "warning",
                },
            ],
            "recommended_actions": [
                {
                    "label": " output contract override ",
                    "detail": "Should be discarded.",
                    "evidence_refs": [],
                },
                {
                    "label": "Review Attribution Drivers",
                    "detail": " Open Attribution Detail before the client discussion. ",
                    "evidence_refs": [{}],
                },
            ],
            "risks_and_exceptions": [
                {
                    "headline": " Attribution remains partial. ",
                    "detail": " Keep to available facts only. ",
                    "tone": "warning",
                    "evidence_refs": [
                        {
                            "metric_label": "Attribution",
                            "metric_value": "Partial",
                            "source_ref": "lotus-gateway:workbench:performance-summary:YTD",
                        }
                    ],
                }
            ],
        },
        output_message="ignored once structured output is valid",
        context_payload=_advisor_context(),
        source_refs=["lotus-gateway:workbench:performance-summary:YTD"],
    )

    talking_points = result.structured_output["talking_points"]
    actions = result.structured_output["recommended_actions"]
    risks = result.structured_output["risks_and_exceptions"]

    assert len(talking_points) == 1
    assert talking_points[0]["tone"] == "neutral"
    assert talking_points[0]["evidence_refs"] == [
        {
            "metric_label": "Active Return",
            "metric_value": "-6.68%",
            "source_ref": "lotus-gateway:workbench:performance-summary:YTD",
        }
    ]
    assert len(actions) == 1
    assert actions[0]["label"] == "Review Attribution Drivers"
    assert actions[0]["detail"] == "Open Attribution Detail before the client discussion."
    assert actions[0]["evidence_refs"] == []
    assert risks[0]["headline"] == "Attribution remains partial."
    assert risks[0]["detail"] == "Keep to available facts only."


def test_normalize_advisor_brief_output_returns_unavailable_when_stub_cannot_build_result() -> None:
    result = normalize_advisor_brief_output(
        parsed_output=None,
        output_message="not json",
        context_payload={"portfolio": {}, "period": {}},
        source_refs=[],
    )

    assert result.guardrail_triggered is True
    assert result.message.startswith("Advisor brief unavailable:")
    assert result.structured_output["talking_points"] == []


def test_extract_grounded_summary_fragment_handles_invalid_or_missing_fragments() -> None:
    assert extract_grounded_summary_fragment("no grounded summary here") is None
    assert extract_grounded_summary_fragment('{"grounded_summary":"unterminated\\x"}') is None
