"""Audit Main Releasability coverage of every commit on main (issues #236, #372, #373).

The merged-PR dispatcher fires once per pull request; this repository merges by
rebase, so a PR of N commits puts N commits on main. This audit proves what is
true of each one, and it FAILS CLOSED: anything that leaves a commit's state
unknown is never reported as covered.

It answers two questions separately, because collapsing them hid real defects
in both directions:

  COVERAGE - does a terminal, evaluated verdict exist for this commit?
  OUTCOME  - if one exists, did the tree pass or fail?

The previous version answered neither honestly. `status != "completed"` put
absent, queued and running into one bucket printed as `GAP`, so a gate still
executing was indistinguishable from one that never ran - and the audit failed
daily on commits whose gates were mid-flight. In the other direction
`{"success", "failure", "timed_out"}` were all "verdict-bearing", so a commit
whose gate FAILED counted as covered and the audit printed `50/50` and exited
0 while three commits sat red on main (#373).

The seven states below are the smallest set that keeps those apart, and each
implies a different action:

  PASSED               a terminal run evaluated the tree and it passed
  FAILED               a terminal run evaluated the tree and it failed
                       (`timed_out` is here: conclusively failed is information)
  ABSENT               no run exists - needs a dispatch
  PENDING              a run exists, has not concluded, within the age limit
  STALE                a run exists, has not concluded, past the age limit -
                       an indefinitely running gate must never become evidence
  UNEVALUATED          a run concluded WITHOUT evaluating: cancelled, skipped,
                       neutral, action_required. Terminal but says nothing.
  EVIDENCE_UNAVAILABLE the listing could not be read for this commit
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

REPOSITORY = "sgajbi/lotus-ai"
WORKFLOW_NAME = "Main Releasability Gate"

PASSED = "PASSED"
FAILED = "FAILED"
ABSENT = "ABSENT"
PENDING = "PENDING"
STALE = "STALE"
UNEVALUATED = "UNEVALUATED"
EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"

# Conclusions that mean the tree was actually evaluated. `neutral`,
# `cancelled`, `skipped` and `action_required` are deliberately absent: they
# conclude without evaluating, and counting them is how a gap hides.
EVALUATED_CONCLUSIONS = {"success": PASSED, "failure": FAILED, "timed_out": FAILED}

# A run is terminal when GitHub says `completed`. Everything else - queued,
# in_progress, requested, waiting, pending - is still moving.
NON_TERMINAL_STATUSES = frozenset({"queued", "in_progress", "requested", "waiting", "pending"})

# Only PASSED and FAILED are coverage: a verdict exists either way. The rest
# leave the commit's state unknown, which is not the same as failing.
COVERED_STATES = frozenset({PASSED, FAILED})


class AuditError(RuntimeError):
    """A condition that leaves the whole audit unknown - always a failure."""


class CommitEvidenceError(RuntimeError):
    """Evidence for one commit could not be read; the audit continues."""


@dataclass(frozen=True)
class CommitState:
    sha: str
    state: str
    detail: str


def _gh(*args: str) -> str:
    if shutil.which("gh") is None:
        raise AuditError("the gh CLI is unavailable, so gate coverage cannot be verified")
    completed = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise CommitEvidenceError(
            f"gh {' '.join(args)} failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:200]}"
        )
    return completed.stdout


def main_commits(limit: int) -> list[str]:
    """The most recent commits on main, newest first, with linear history
    verified DIRECTLY on the audited window.

    The per-commit enumeration is only correct when history is linear. The old
    proxy - asserting the repository's rebase-only merge settings - broke when
    the workflow token stopped being able to read those fields, and the audit
    failed closed daily while real coverage was unknown. Measuring the
    invariant itself is stronger: a merge commit in the window fails the audit
    the day it lands, named by sha, with no dependence on token permissions.
    """

    try:
        raw = _gh(
            "api",
            f"repos/{REPOSITORY}/commits?sha=main&per_page={limit}",
            "--jq",
            r'.[] | "\(.sha) \(.parents | length)"',
        )
    except CommitEvidenceError as error:
        raise AuditError(str(error)) from error

    commits: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, _, parent_count = line.strip().partition(" ")
        # A 0-parent root commit also refuses here; acceptable - this
        # repository's history is far deeper than any audit window, and an
        # audit that reaches the root SHOULD stop rather than trust an
        # enumeration premise it can no longer distinguish.
        if parent_count != "1":
            raise AuditError(
                f"main commit {sha} has {parent_count} parents; the per-commit "
                "enumeration assumes linear (rebase-only) history - audit the "
                "merge that produced it before trusting gate coverage"
            )
        commits.append(sha)
    if not commits:
        raise AuditError("no commits returned for main; coverage is unknown")
    return commits


def _runs_for(commit_sha: str) -> list[dict[str, object]]:
    raw = _gh(
        "run",
        "list",
        "--repo",
        REPOSITORY,
        "--commit",
        commit_sha,
        "--workflow",
        WORKFLOW_NAME,
        "--json",
        "status,conclusion,createdAt,databaseId,attempt",
    )
    return json.loads(raw or "[]")


def _sort_key(run: dict[str, object]) -> tuple[str, int, int]:
    """Newest first by created time, then by attempt, then by run id.

    A rerun of the same run increments `attempt` and keeps `databaseId`; a
    re-dispatch creates a new `databaseId`. Ordering on all three means the
    reported outcome is the latest evidence under either mechanism, rather
    than depending on which one produced it.
    """

    return (
        str(run.get("createdAt") or ""),
        int(run.get("attempt") or 0),
        int(run.get("databaseId") or 0),
    )


def classify(
    runs: list[dict[str, object]],
    *,
    now: datetime,
    pending_max_age: timedelta,
) -> CommitState:
    """Decide one commit's state from its runs. Pure - no I/O, no clock."""

    if not runs:
        return CommitState("", ABSENT, "no Main Releasability Gate run exists")

    ordered = sorted(runs, key=_sort_key, reverse=True)

    # A terminal, evaluated verdict is the strongest evidence available, and
    # the most recent one decides. A rerun still in flight does not erase a
    # recorded pass or fail - it is reported alongside, not instead.
    for run in ordered:
        if run.get("status") != "completed":
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion in EVALUATED_CONCLUSIONS:
            state = EVALUATED_CONCLUSIONS[conclusion]
            in_flight = any(other.get("status") in NON_TERMINAL_STATUSES for other in ordered)
            suffix = "; a later run is still in flight" if in_flight else ""
            return CommitState(
                "", state, f"conclusion={conclusion}, attempt={run.get('attempt')}{suffix}"
            )

    unconcluded = [run for run in ordered if run.get("status") in NON_TERMINAL_STATUSES]
    if unconcluded:
        newest = unconcluded[0]
        created = _parse_time(newest.get("createdAt"))
        if created is None:
            return CommitState(
                "", STALE, f"status={newest.get('status')} with an unreadable createdAt"
            )
        age = now - created
        if age <= pending_max_age:
            return CommitState("", PENDING, f"status={newest.get('status')}, age={_minutes(age)}m")
        return CommitState(
            "",
            STALE,
            f"status={newest.get('status')}, age={_minutes(age)}m "
            f"exceeds the {_minutes(pending_max_age)}m limit",
        )

    # Terminal runs exist but none evaluated the tree.
    conclusions = sorted({str(run.get("conclusion") or "none") for run in ordered})
    return CommitState("", UNEVALUATED, f"terminal without evaluating: {', '.join(conclusions)}")


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def state_for_commit(
    commit_sha: str,
    *,
    now_provider: object,
    pending_max_age: timedelta,
    recheck_attempts: int,
    recheck_delay_seconds: float,
    sleep: object,
) -> CommitState:
    """Classify one commit, rechecking a PENDING result a bounded number of times.

    The recheck is bounded on purpose. An unbounded wait turns the audit into
    something that can hang, and a gate that never concludes must not be able
    to hold the audit open until it looks like evidence - it ages into STALE
    instead.
    """

    attempts = max(1, recheck_attempts)
    state = CommitState(commit_sha, ABSENT, "")
    for attempt in range(attempts):
        try:
            runs = _runs_for(commit_sha)
        except CommitEvidenceError as error:
            return CommitState(commit_sha, EVIDENCE_UNAVAILABLE, str(error))
        state = classify(runs, now=now_provider(), pending_max_age=pending_max_age)
        state = CommitState(commit_sha, state.state, state.detail)
        if state.state != PENDING:
            return state
        if attempt < attempts - 1:
            sleep(recheck_delay_seconds)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="exit non-zero when any commit lacks a terminal evaluated verdict",
    )
    parser.add_argument(
        "--fail-on-failed-verdict",
        action="store_true",
        help="exit non-zero when any commit's gate concluded failure or timed_out",
    )
    parser.add_argument(
        "--pending-max-age-minutes",
        type=int,
        default=90,
        help="a still-running gate older than this is STALE, never accepted evidence",
    )
    parser.add_argument("--recheck-attempts", type=int, default=1)
    parser.add_argument("--recheck-delay-seconds", type=float, default=20.0)
    arguments = parser.parse_args()

    try:
        commits = main_commits(arguments.limit)
    except AuditError as error:
        print(f"main gate coverage audit FAILED: {error}")
        return 1

    pending_max_age = timedelta(minutes=arguments.pending_max_age_minutes)
    states = [
        state_for_commit(
            sha,
            now_provider=lambda: datetime.now(timezone.utc),
            pending_max_age=pending_max_age,
            recheck_attempts=arguments.recheck_attempts,
            recheck_delay_seconds=arguments.recheck_delay_seconds,
            sleep=time.sleep,
        )
        for sha in commits
    ]

    counts = {
        name: sum(1 for state in states if state.state == name)
        for name in (
            PASSED,
            FAILED,
            ABSENT,
            PENDING,
            STALE,
            UNEVALUATED,
            EVIDENCE_UNAVAILABLE,
        )
    }
    covered = sum(1 for state in states if state.state in COVERED_STATES)

    # Coverage and outcome are printed as separate numbers, because a commit
    # can be covered and red. Reporting one number was how three failing
    # commits sat behind "50/50".
    print(f"main gate coverage: {covered}/{len(states)} commits carry a terminal verdict")
    print(f"  outcome of those: {counts[PASSED]} passed, {counts[FAILED]} failed")
    print(
        f"  not covered: {counts[ABSENT]} absent, {counts[PENDING]} pending, "
        f"{counts[STALE]} stale, {counts[UNEVALUATED]} unevaluated, "
        f"{counts[EVIDENCE_UNAVAILABLE]} evidence-unavailable"
    )
    for state in states:
        if state.state in (PASSED,):
            continue
        print(f"  {state.state:20} {state.sha}  {state.detail}")

    gap = len(states) - covered
    exit_code = 0
    if gap and arguments.fail_on_gap:
        exit_code = 1
    if counts[FAILED] and arguments.fail_on_failed_verdict:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
