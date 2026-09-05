"""Audit Main Releasability coverage of every commit on main (issue #236).

The merged-PR dispatcher fires once per pull request; this repository
merges by rebase, so a PR of N commits puts N commits on main. This audit
proves every one of them carries a verdict-bearing gate run, and it FAILS
CLOSED: an unreadable run listing, a missing tool, or a run that reached
no verdict (cancelled, skipped, still running) is a gap, never a pass.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

REPOSITORY = "sgajbi/lotus-ai"
WORKFLOW_NAME = "Main Releasability Gate"
# A verdict is a conclusion that actually evaluated the tree. "neutral" is
# deliberately absent: it concludes without evaluating, so counting it would
# mask exactly the gap this audit exists to find. "timed_out" stays - it is
# conclusively failed, which is information.
VERDICT_CONCLUSIONS = frozenset({"success", "failure", "timed_out"})


class AuditError(RuntimeError):
    """Any condition that leaves coverage unknown - always a failure."""


def _gh(*args: str) -> str:
    if shutil.which("gh") is None:
        raise AuditError("the gh CLI is unavailable, so gate coverage cannot be verified")
    completed = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AuditError(
            f"gh {' '.join(args)} failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:300]}"
        )
    return completed.stdout


def main_commits(limit: int) -> list[str]:
    """The most recent commits on main, newest first - with linear history
    verified DIRECTLY on the audited window.

    The per-commit enumeration is only correct when history is linear. The
    old proxy (asserting the repository's rebase-only merge settings) broke
    when the workflow token stopped being able to read those fields - every
    ``allow_*`` value returned null and the audit failed closed daily while
    real coverage was unknown. Measuring the invariant itself is stronger:
    a merge commit in the window fails the audit the day it lands, named by
    sha, with no dependence on token permissions or settings drift.
    """

    raw = _gh(
        "api",
        f"repos/{REPOSITORY}/commits?sha=main&per_page={limit}",
        "--jq",
        r'.[] | "\(.sha) \(.parents | length)"',
    )
    commits: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, _, parent_count = line.strip().partition(" ")
        # A 0-parent root commit would also refuse here; acceptable - this
        # repository's history is far deeper than any audit window, and an
        # audit that somehow reaches the root SHOULD stop rather than trust
        # an enumeration premise it can no longer distinguish.
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


def has_verdict_bearing_run(commit_sha: str) -> bool:
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
        "status,conclusion",
    )
    runs = json.loads(raw or "[]")
    return any(
        run.get("status") == "completed" and run.get("conclusion") in VERDICT_CONCLUSIONS
        for run in runs
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="exit non-zero when any commit lacks a verdict-bearing gate run",
    )
    arguments = parser.parse_args()

    try:
        commits = main_commits(arguments.limit)
        gaps = [sha for sha in commits if not has_verdict_bearing_run(sha)]
    except AuditError as error:
        # Fail closed: unknown coverage is never reported as covered.
        print(f"main gate coverage audit FAILED: {error}")
        return 1

    print(f"main gate coverage: {len(commits) - len(gaps)}/{len(commits)} commits verdict-bearing")
    for sha in gaps:
        print(f"  GAP {sha}")
    if gaps and arguments.fail_on_gap:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
