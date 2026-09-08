"""Every audit state is distinguishable from every other (issues #372, #373).

The audit previously answered two different questions with one word and got
both wrong. `status != "completed"` put ABSENT, PENDING and STALE into a single
`GAP`, so a gate mid-flight was indistinguishable from one that never ran. And
`{"success", "failure", "timed_out"}` were all "verdict-bearing", so a commit
whose gate FAILED counted as covered - the audit printed `50/50` and exited 0
while three commits sat red on main.

These are behavioural: each drives `classify` or `state_for_commit` with the run
listing GitHub would actually return and asserts the state that follows. The
pair-wise test at the end is the one that would have caught the original
defect, because it asserts the states DIFFER rather than asserting each in
isolation - two collapsed states each pass their own test.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import audit_main_gate_coverage as audit  # type: ignore[import-not-found]  # noqa: E402

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
AGE_LIMIT = timedelta(minutes=90)


def _run(**overrides: object) -> dict[str, object]:
    run = {
        "status": "completed",
        "conclusion": "success",
        "createdAt": "2026-09-08T11:00:00Z",
        "databaseId": 1,
        "attempt": 1,
    }
    run.update(overrides)
    return run


def _classify(runs: list[dict[str, object]], *, now: datetime = NOW) -> str:
    return str(audit.classify(runs, now=now, pending_max_age=AGE_LIMIT).state)


def test_no_run_at_all_is_absent() -> None:
    assert _classify([]) == audit.ABSENT


def test_a_queued_run_is_pending_not_absent() -> None:
    assert _classify([_run(status="queued", conclusion=None)]) == audit.PENDING


def test_a_running_gate_is_pending_not_absent() -> None:
    assert _classify([_run(status="in_progress", conclusion=None)]) == audit.PENDING


def test_a_run_pending_past_the_age_limit_is_stale() -> None:
    """An indefinitely running gate must never become accepted evidence."""

    old = _run(status="in_progress", conclusion=None, createdAt="2026-09-08T09:00:00Z")

    assert _classify([old]) == audit.STALE


def test_the_age_limit_is_the_boundary_not_a_gesture() -> None:
    just_inside = _run(status="in_progress", conclusion=None, createdAt="2026-09-08T10:31:00Z")
    just_outside = _run(status="in_progress", conclusion=None, createdAt="2026-09-08T10:29:00Z")

    assert _classify([just_inside]) == audit.PENDING
    assert _classify([just_outside]) == audit.STALE


def test_a_successful_gate_is_passed() -> None:
    assert _classify([_run(conclusion="success")]) == audit.PASSED


@pytest.mark.parametrize("conclusion", ["failure", "timed_out"])
def test_a_failing_or_timed_out_gate_is_failed_not_coverage(conclusion: str) -> None:
    """The defect behind #373: these counted as covered and the audit exited 0."""

    assert _classify([_run(conclusion=conclusion)]) == audit.FAILED


@pytest.mark.parametrize("conclusion", ["cancelled", "skipped", "neutral", "action_required"])
def test_a_terminal_run_that_evaluated_nothing_is_unevaluated(conclusion: str) -> None:
    """Terminal is not the same as evaluated. `neutral` concludes without
    running the tree, and counting it is exactly how a gap hides."""

    assert _classify([_run(conclusion=conclusion)]) == audit.UNEVALUATED


def test_cancellation_is_not_a_pass_and_not_a_gap_it_is_its_own_state() -> None:
    assert _classify([_run(conclusion="cancelled")]) == audit.UNEVALUATED
    assert audit.UNEVALUATED not in audit.COVERED_STATES


def test_only_passed_and_failed_count_as_coverage() -> None:
    """Coverage means a verdict exists, either way. It is not 'the gate is green'."""

    assert audit.COVERED_STATES == {audit.PASSED, audit.FAILED}
    for state in (
        audit.ABSENT,
        audit.PENDING,
        audit.STALE,
        audit.UNEVALUATED,
        audit.EVIDENCE_UNAVAILABLE,
    ):
        assert state not in audit.COVERED_STATES


def test_the_latest_attempt_decides_the_outcome() -> None:
    """A rerun increments `attempt` on the same run id; the newer one wins."""

    first = _run(conclusion="failure", attempt=1, databaseId=7)
    rerun = _run(conclusion="success", attempt=2, databaseId=7)

    assert _classify([first, rerun]) == audit.PASSED
    assert _classify([rerun, first]) == audit.PASSED, "order of the listing must not matter"


def test_a_redispatch_with_a_new_run_id_also_decides_by_recency() -> None:
    older = _run(conclusion="success", createdAt="2026-09-08T09:00:00Z", databaseId=1)
    newer = _run(conclusion="failure", createdAt="2026-09-08T11:00:00Z", databaseId=2)

    assert _classify([older, newer]) == audit.FAILED


def test_a_rerun_in_flight_does_not_erase_a_recorded_verdict() -> None:
    """A terminal verdict stays the reported outcome, with the in-flight run
    named in the detail rather than replacing it."""

    recorded = _run(conclusion="failure", attempt=1)
    in_flight = _run(status="in_progress", conclusion=None, attempt=2)

    result = audit.classify([recorded, in_flight], now=NOW, pending_max_age=AGE_LIMIT)

    assert result.state == audit.FAILED
    assert "still in flight" in result.detail


def test_an_unreadable_created_time_on_a_pending_run_is_stale_not_pending() -> None:
    """Fail closed: an age that cannot be computed must not read as young."""

    assert _classify([_run(status="in_progress", conclusion=None, createdAt=None)]) == audit.STALE


def test_api_failure_for_one_commit_is_evidence_unavailable_not_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A listing that cannot be read is unknown, and unknown is never coverage."""

    def explode(_sha: str) -> list[dict[str, object]]:
        raise audit.CommitEvidenceError("gh run list failed with exit 4")

    monkeypatch.setattr(audit, "_runs_for", explode)

    state = audit.state_for_commit(
        "a" * 40,
        now_provider=lambda: NOW,
        pending_max_age=AGE_LIMIT,
        recheck_attempts=1,
        recheck_delay_seconds=0.0,
        sleep=lambda _seconds: None,
    )

    assert state.state == audit.EVIDENCE_UNAVAILABLE
    assert state.state not in audit.COVERED_STATES


def test_a_pending_run_that_concludes_during_recheck_is_reported_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pending-to-terminal transition, which is why rechecks exist."""

    listings = [
        [_run(status="in_progress", conclusion=None)],
        [_run(status="completed", conclusion="success")],
    ]
    monkeypatch.setattr(audit, "_runs_for", lambda _sha: listings.pop(0))
    slept: list[float] = []

    state = audit.state_for_commit(
        "b" * 40,
        now_provider=lambda: NOW,
        pending_max_age=AGE_LIMIT,
        recheck_attempts=2,
        recheck_delay_seconds=5.0,
        sleep=slept.append,
    )

    assert state.state == audit.PASSED
    assert slept == [5.0], "it must wait between rechecks, once"


def test_rechecks_are_bounded_so_a_stuck_gate_cannot_hold_the_audit_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gate that never concludes must not be able to wait until it looks
    like evidence. It stays PENDING here and ages into STALE on a later run."""

    calls: list[int] = []

    def always_running(_sha: str) -> list[dict[str, object]]:
        calls.append(1)
        return [_run(status="in_progress", conclusion=None)]

    monkeypatch.setattr(audit, "_runs_for", always_running)

    state = audit.state_for_commit(
        "c" * 40,
        now_provider=lambda: NOW,
        pending_max_age=AGE_LIMIT,
        recheck_attempts=3,
        recheck_delay_seconds=0.0,
        sleep=lambda _seconds: None,
    )

    assert state.state == audit.PENDING
    assert len(calls) == 3, "bounded: exactly the configured attempts, then it stops"
    assert state.state not in audit.COVERED_STATES


def test_a_terminal_result_stops_rechecking_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def concluded(_sha: str) -> list[dict[str, object]]:
        calls.append(1)
        return [_run(conclusion="failure")]

    monkeypatch.setattr(audit, "_runs_for", concluded)

    state = audit.state_for_commit(
        "d" * 40,
        now_provider=lambda: NOW,
        pending_max_age=AGE_LIMIT,
        recheck_attempts=5,
        recheck_delay_seconds=0.0,
        sleep=lambda _seconds: None,
    )

    assert state.state == audit.FAILED
    assert len(calls) == 1


def test_every_state_is_distinguishable_from_every_other() -> None:
    """The test that would have caught the original defect.

    Each state asserted in isolation still passes when two of them are
    collapsed into one word - that is precisely what happened, twice. This
    asserts the mapping is injective: seven inputs, seven distinct answers.
    """

    inputs = {
        audit.ABSENT: [],
        audit.PENDING: [_run(status="in_progress", conclusion=None)],
        audit.STALE: [
            _run(status="in_progress", conclusion=None, createdAt="2026-09-08T08:00:00Z")
        ],
        audit.PASSED: [_run(conclusion="success")],
        audit.FAILED: [_run(conclusion="failure")],
        audit.UNEVALUATED: [_run(conclusion="cancelled")],
    }

    observed = {expected: _classify(runs) for expected, runs in inputs.items()}

    assert observed == {expected: expected for expected in inputs}
    assert len(set(observed.values())) == len(inputs), "states must not collapse"
