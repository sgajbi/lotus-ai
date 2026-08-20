from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def test_merged_pr_main_releasability_dispatcher_targets_main_gate() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "pull_request_target:" in text
    assert "types: [closed]" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.base.ref == 'main'" in text
    assert "timeout-minutes: 10" in text
    assert "gh workflow run main-releasability.yml" in text
    assert "--ref main" in text
    assert "github.event.pull_request.merge_commit_sha" in text
    assert '-f expected_sha="$MERGE_COMMIT_SHA"' in text
    assert '-f triggering_pr="$PR_NUMBER"' in text


def test_main_releasability_gate_is_dispatchable_without_duplicate_push_trigger() -> None:
    workflow = WORKFLOW_DIR / "main-releasability.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "expected_sha:" in text
    assert "triggering_pr:" in text
    assert "git rev-parse HEAD" in text
    assert "push:" not in text
    assert 'branches: [ "main" ]' not in text
    assert "name: Main Releasability Gate" in text
