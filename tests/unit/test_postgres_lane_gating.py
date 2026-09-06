"""The PostgreSQL fence lane fails closed (issue #344).

The lane's value depends entirely on it being unskippable in CI: a gate that
skips when its database is missing reports green while proving nothing. These
pin the four postures without needing a database.
"""

from __future__ import annotations

from tests.support.postgres_lane import decide_lane_start, decide_unreachable

_PG_URL = "postgresql+psycopg://lotus_ai:lotus_ai@localhost:5432/lotus_ai"


def test_required_without_a_url_fails_rather_than_skips() -> None:
    decision = decide_lane_start(url=None, required=True)
    assert decision.action == "fail"
    assert "must not silently skip" in decision.reason
    # Whitespace is not a configured URL either.
    assert decide_lane_start(url="   ", required=True).action == "fail"


def test_unreachable_database_fails_in_ci_and_skips_locally() -> None:
    assert decide_unreachable(required=True, error="connection refused").action == "fail"
    local = decide_unreachable(required=False, error="connection refused")
    assert local.action == "skip"
    assert "connection refused" in local.reason


def test_a_non_postgres_url_always_fails() -> None:
    """Pointing the lane at SQLite would make it tautological rather than
    absent - it must refuse, required or not."""

    for required in (True, False):
        decision = decide_lane_start(url="sqlite:///lane.db", required=required)
        assert decision.action == "fail"
        assert "production engine" in decision.reason


def test_local_run_skips_with_an_actionable_reason_and_configured_runs_proceed() -> None:
    skipped = decide_lane_start(url=None, required=False)
    assert skipped.action == "skip"
    assert "LOTUS_AI_POSTGRES_TEST_URL" in skipped.reason
    assert decide_lane_start(url=_PG_URL, required=False).action == "run"
    assert decide_lane_start(url=f"  {_PG_URL}  ", required=True).action == "run"
