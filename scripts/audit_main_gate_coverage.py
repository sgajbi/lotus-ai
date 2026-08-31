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
VERDICT_CONCLUSIONS = frozenset({"success", "failure", "timed_out", "neutral"})


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


def assert_rebase_only_merging() -> None:
    """The per-commit enumeration is only correct under rebase merging."""

    raw = _gh(
        "api",
        f"repos/{REPOSITORY}",
        "--jq",
        "{squash: .allow_squash_merge, merge: .allow_merge_commit, rebase: .allow_rebase_merge}",
    )
    settings = json.loads(raw)
    if settings != {"squash": False, "merge": False, "rebase": True}:
        raise AuditError(
            "main-gate coverage assumes rebase-only merging; repository merge settings are "
            f"{settings} - update the dispatcher enumeration before changing them"
        )


def main_commits(limit: int) -> list[str]:
    raw = _gh(
        "api",
        f"repos/{REPOSITORY}/commits?sha=main&per_page={limit}",
        "--jq",
        ".[].sha",
    )
    commits = [line.strip() for line in raw.splitlines() if line.strip()]
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
        assert_rebase_only_merging()
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
