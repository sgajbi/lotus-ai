"""Gating decisions for the PostgreSQL fence lane (issue #344).

Extracted from the lane's conftest so the fail-closed postures are provable
in the fast lane, without a database: a gate whose failure mode is only
ever exercised by accident is a gate nobody has checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

URL_VARIABLE = "LOTUS_AI_POSTGRES_TEST_URL"
REQUIRED_VARIABLE = "LOTUS_AI_POSTGRES_TEST_REQUIRED"

LaneAction = Literal["run", "fail", "skip"]


@dataclass(frozen=True)
class LaneDecision:
    action: LaneAction
    reason: str = ""


def decide_lane_start(*, url: str | None, required: bool) -> LaneDecision:
    """Decide the lane's posture from configuration alone.

    Fail-closed: when the lane is REQUIRED (CI), a missing URL fails rather
    than skips - a silently skipped gate reports as a pass. A non-PostgreSQL
    URL always fails, required or not: this lane exists to prove the fences
    on the production engine, and pointing it at SQLite would make it
    tautological rather than absent.
    """

    normalized = (url or "").strip()
    if not normalized:
        if required:
            return LaneDecision(
                "fail",
                f"{REQUIRED_VARIABLE} is set but {URL_VARIABLE} is not: the "
                "PostgreSQL fence lane must not silently skip in CI.",
            )
        return LaneDecision(
            "skip",
            f"set {URL_VARIABLE} to a disposable PostgreSQL "
            "(e.g. postgresql+psycopg://lotus_ai:lotus_ai@localhost:5432/lotus_ai) "
            "to run the fence proofs locally",
        )
    if not normalized.startswith("postgresql"):
        return LaneDecision(
            "fail",
            f"{URL_VARIABLE} must point at PostgreSQL - this lane exists to "
            f"prove the fences on the production engine, got: {normalized!r}",
        )
    return LaneDecision("run")


def decide_unreachable(*, required: bool, error: str) -> LaneDecision:
    """Decide the posture when the configured database cannot be reached."""

    if required:
        return LaneDecision("fail", f"PostgreSQL at {URL_VARIABLE} is unreachable in CI: {error}")
    return LaneDecision("skip", f"PostgreSQL at {URL_VARIABLE} is unreachable: {error}")
