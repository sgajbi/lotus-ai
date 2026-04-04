from app.providers.advisor_brief_stub import build_advisor_brief_stub_result


def _advisor_context_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "portfolio": {
            "portfolio_id": "PB_SG_GLOBAL_BAL_001",
            "portfolio_name": "PB SG Global Balanced",
        },
        "period": {"period": "YTD"},
        "performance": {
            "portfolio_return_pct": 1.25,
            "benchmark_return_pct": 7.93,
            "active_return_pct": -6.68,
        },
        "contribution": {
            "top_positions": [
                {"position_id": "AAPL US", "total_contribution_pct": 0.3},
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
        "Advisor brief for PB_SG_GLOBAL_BAL_001: YTD portfolio return is 1.25%; "
        "benchmark return is 7.93%; active return is -6.68%; "
        "top contributor is AAPL US; largest attribution effect is Asset Class / Equity."
    )
    assert structured_output == {
        "advisor_brief_status": "partial",
        "coverage_state": "partial",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "period": "YTD",
        "source_refs": [
            "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD",
            "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-details:YTD",
        ],
        "grounded_summary": message,
        "grounded_facts": [
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
        ],
    }


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


def test_build_advisor_brief_stub_result_ignores_non_advisor_payload_shape() -> None:
    assert (
        build_advisor_brief_stub_result(
            context_payload={"status": "BLOCKED", "violations": 2},
            source_refs=["lotus-manage:run:reb_002"],
        )
        is None
    )
