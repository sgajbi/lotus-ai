"""The main-gate coverage audit fails closed (issue #236).

An audit that reports success when it could not verify anything is worse
than no audit: it manufactures false assurance. These tests pin the
failure modes - missing tool, unreadable listings, a merge commit breaking
the linear-history enumeration premise, and runs that reached no verdict.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import audit_main_gate_coverage as audit  # type: ignore[import-not-found]  # noqa: E402


class _Completed:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _fake_gh(monkeypatch: pytest.MonkeyPatch, responses: dict[str, object]) -> None:
    monkeypatch.setattr(audit.shutil, "which", lambda _name: "/usr/bin/gh")

    def run(args: list[str], **_kwargs: object) -> _Completed:
        key = next((name for name in responses if name in " ".join(args)), None)
        if key is None:
            return _Completed(returncode=1, stderr="unexpected call")
        value = responses[key]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, _Completed):
            return value
        return _Completed(stdout=str(value))

    monkeypatch.setattr(audit.subprocess, "run", run)


def test_a_missing_gh_cli_is_a_failure_not_a_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit.shutil, "which", lambda _name: None)
    monkeypatch.setattr(sys, "argv", ["audit", "--fail-on-gap"])
    assert audit.main() == 1


def test_a_merge_commit_in_the_window_refuses_to_trust_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-commit enumeration is only correct over linear history - the
    audit measures that invariant directly (the old proxy asserted the
    repository's merge settings, which the workflow token can no longer
    read). A two-parent commit refuses the whole audit, named by sha."""

    _fake_gh(monkeypatch, {"repos/sgajbi/lotus-ai/commits": "abc123 2\ndef456 1\n"})
    monkeypatch.setattr(sys, "argv", ["audit", "--fail-on-gap"])
    assert audit.main() == 1


def test_unreadable_run_listing_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_gh(
        monkeypatch,
        {
            "repos/sgajbi/lotus-ai/commits": "abc123 1\n",
            "run": _Completed(returncode=1, stderr="API rate limit exceeded"),
        },
    )
    monkeypatch.setattr(sys, "argv", ["audit", "--fail-on-gap"])
    assert audit.main() == 1


def test_a_run_without_a_verdict_does_not_count_as_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_gh(
        monkeypatch,
        {
            "repos/sgajbi/lotus-ai/commits": "abc123 1\n",
            "run": json.dumps([{"status": "completed", "conclusion": "cancelled"}]),
        },
    )
    monkeypatch.setattr(sys, "argv", ["audit", "--fail-on-gap"])
    assert audit.main() == 1


def test_a_verdict_bearing_run_is_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_gh(
        monkeypatch,
        {
            "repos/sgajbi/lotus-ai/commits": "abc123 1\n",
            "run": json.dumps([{"status": "completed", "conclusion": "success"}]),
        },
    )
    monkeypatch.setattr(sys, "argv", ["audit", "--fail-on-gap"])
    assert audit.main() == 0


def test_an_empty_commit_listing_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_gh(
        monkeypatch,
        {
            "repos/sgajbi/lotus-ai/commits": "\n",
        },
    )
    monkeypatch.setattr(sys, "argv", ["audit", "--fail-on-gap"])
    assert audit.main() == 1


def test_the_dispatcher_gates_every_commit_of_a_pull_request() -> None:
    """The workflow enumerates the PR's commits and asserts rebase-only
    merging, so an N-commit PR cannot leave N-1 commits ungated."""

    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "merged-pr-main-releasability.yml"
    ).read_text(encoding="utf-8")
    assert "PR_COMMIT_COUNT" in workflow
    assert "false,false,true" in workflow
    # One dispatch job per merged commit, fed by the enumeration job, so the
    # proven single-commit dispatch body runs unchanged for every commit.
    assert "fromJSON(needs.enumerate-merged-commits.outputs.commit_shas)" in workflow
    assert "MERGE_COMMIT_SHA: ${{ matrix.commit_sha }}" in workflow


def test_gate_evidence_runs_queue_rather_than_cancelling() -> None:
    """A cancelled run reaches no verdict, so cancel-in-progress on the gate
    would silently delete the only proof a commit was validated - and the
    coverage audit would then correctly report a gap that nobody caused."""

    workflow = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "main-releasability.yml"
    ).read_text(encoding="utf-8")
    assert "cancel-in-progress: false" in workflow
    assert "cancel-in-progress: true" not in workflow
