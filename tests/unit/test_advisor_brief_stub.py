from app.providers.advisor_brief_stub import build_advisor_brief_stub_result


def _advisor_context_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "portfolio": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "display_label": "PB SG GLOBAL BAL 001",
            "portfolio_name": "PB SG Global Balanced",
        },
        "period": {"period": "YTD"},
        "performance": {
            "portfolio_return_pct": 1.25,
            "benchmark_return_pct": 7.93,
            "active_return_pct": -6.68,
            "net_cash_flow": 14_725,
            "end_market_value": 1_087_461,
            "money_weighted_return_pct": 1.23,
        },
        "contribution": {
            "top_positions": [
                {
                    "position_id": "PB_SG_GLOBAL_BAL_001:FO_EQ_AAPL_US",
                    "display_label": "AAPL US",
                    "contribution_pct": 0.3,
                    "total_return_pct": 4.31,
                },
            ],
            "bottom_positions": [
                {
                    "position_id": "PB_SG_GLOBAL_BAL_001:FO_CASH_USD_BOOK_OPERATING",
                    "display_label": "USD BOOK OPERATING",
                    "contribution_pct": -0.06,
                    "total_return_pct": 0.0,
                },
            ],
        },
        "attribution": {
            "top_effects": [
                {"key_label": "Asset Class / Equity", "total_effect_pct": -4.1},
            ],
        },
        "supportability": [
            {"key": "performance_context", "value": "ready"},
            {"key": "evidence", "value": "partial"},
        ],
    }
    payload.update(overrides)
    return payload


def test_build_advisor_brief_stub_result_returns_source_grounded_summary() -> None:
    result = build_advisor_brief_stub_result(
        context_payload=_advisor_context_payload(),
        source_refs=[
            "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
            "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-details:YTD",
        ],
    )

    assert result is not None
    message, structured_output = result

    assert message == (
        "PB SG GLOBAL BAL 001 delivered 1.25% over YTD versus 7.93% for the benchmark, "
        "resulting in -6.68% active return. net flow was $14,725 and ending market value "
        "was $1,087,461. largest contribution came from AAPL US (0.30%) while the main "
        "drag was USD BOOK OPERATING (-0.06%). largest benchmark-relative attribution "
        "effect was Asset Class / Equity (-4.10%)."
    )
    assert structured_output["advisor_brief_status"] == "partial"
    assert structured_output["coverage_state"] == "partial"
    assert structured_output["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
    assert structured_output["period"] == "YTD"
    assert structured_output["source_refs"] == [
        "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-details:YTD",
    ]
    assert structured_output["grounded_summary"] == message
    assert structured_output["talking_points"][1] == {
        "headline": "Largest contribution came from AAPL US.",
        "detail": (
            "AAPL US contributed 0.30% with return 4.31%. Main drag came from "
            "USD BOOK OPERATING at -0.06%."
        ),
        "tone": "positive",
        "evidence_refs": [
            {
                "metric_label": "Top Contributor",
                "metric_value": "0.30%",
                "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-details:YTD",
            }
        ],
    }
    assert structured_output["recommended_actions"][1]["label"] == "Investigate USD BOOK OPERATING"
    assert structured_output["risks_and_exceptions"][0]["headline"] == "evidence is partial."
    assert structured_output["grounded_facts"] == [
        {
            "metric_label": "Portfolio Return",
            "metric_value": "1.25%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
        {
            "metric_label": "Benchmark Return",
            "metric_value": "7.93%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
        {
            "metric_label": "Active Return",
            "metric_value": "-6.68%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
        {
            "metric_label": "Money-Weighted Return",
            "metric_value": "1.23%",
            "source_ref": "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
        },
    ]


def test_build_advisor_brief_stub_result_refuses_when_source_refs_are_missing() -> None:
    result = build_advisor_brief_stub_result(
        context_payload=_advisor_context_payload(),
        source_refs=[],
    )

    assert result is not None
    message, structured_output = result

    assert message == (
        "Advisor brief unavailable: source performance facts or source references are "
        "insufficient for a grounded explanation."
    )
    assert structured_output["advisor_brief_status"] == "unavailable"
    assert structured_output["coverage_state"] == "partial"
    assert structured_output["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
    assert structured_output["period"] == "YTD"
    assert structured_output["source_refs"] == []
    assert structured_output["grounded_summary"] == message
    assert structured_output["grounded_facts"] == []
    assert structured_output["talking_points"] == []
    assert structured_output["recommended_actions"] == []
    assert structured_output["risks_and_exceptions"][0]["headline"] == "Advisor Brief is unavailable."


def test_build_advisor_brief_stub_result_ignores_non_advisor_payload_shape() -> None:
    assert (
        build_advisor_brief_stub_result(
            context_payload={"status": "BLOCKED", "violations": 2},
            source_refs=["lotus-manage:run:reb_002"],
        )
        is None
    )
