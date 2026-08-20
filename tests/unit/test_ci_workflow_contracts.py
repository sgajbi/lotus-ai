from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
IMMUTABLE_REF_LOOKUP_CONDITION = (
    'if existing_ref_sha="$(gh api '
    '"repos/$GITHUB_REPOSITORY/git/ref/tags/$dispatch_ref" '
    '--jq .object.sha 2>/dev/null)"; then'
)
LOOKUP_FAILURE_RESET_BLOCK = '\n          else\n            existing_ref_sha=""\n          fi\n'


def _merged_pr_dispatch_contract_errors(text: str) -> list[str]:
    errors: list[str] = []
    required_fragments = (
        "pull_request_target:",
        "types: [closed]",
        "actions: write",
        "contents: write",
        "github.event.pull_request.merged == true",
        "github.event.pull_request.base.ref == 'main'",
        "timeout-minutes: 10",
        "set -euo pipefail",
        "github.event.pull_request.merge_commit_sha",
        'dispatch_ref="main-releasability-${MERGE_COMMIT_SHA}"',
        'existing_ref_sha=""',
        IMMUTABLE_REF_LOOKUP_CONDITION,
        "repos/$GITHUB_REPOSITORY/git/refs",
        'ref="refs/tags/$dispatch_ref"',
        "gh workflow run main-releasability.yml",
        '--ref "$dispatch_ref"',
        '-f expected_sha="$MERGE_COMMIT_SHA"',
        '-f triggering_pr="$PR_NUMBER"',
    )
    for fragment in required_fragments:
        if fragment not in text:
            errors.append(f"merged-pr-main-releasability.yml missing `{fragment}`")
    if "--ref main" in text:
        errors.append("merged-pr-main-releasability.yml must not dispatch mutable `--ref main`")
    if "git/ref/tags/$dispatch_ref" in text and IMMUTABLE_REF_LOOKUP_CONDITION not in text:
        errors.append(
            "merged-pr-main-releasability.yml must use the complete immutable-ref lookup "
            "condition ending immediately in `; then`"
        )
    if LOOKUP_FAILURE_RESET_BLOCK not in text:
        errors.append(
            "merged-pr-main-releasability.yml lookup failure arm must only reset "
            "`existing_ref_sha` before the outer `fi`"
        )
    return errors


def test_merged_pr_main_releasability_dispatcher_targets_main_gate() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8")

    assert _merged_pr_dispatch_contract_errors(text) == []


def test_merged_pr_main_releasability_dispatcher_rejects_mutable_ref() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace('--ref "$dispatch_ref"', "--ref main")

    errors = _merged_pr_dispatch_contract_errors(text)

    assert "merged-pr-main-releasability.yml must not dispatch mutable `--ref main`" in errors
    assert 'merged-pr-main-releasability.yml missing `--ref "$dispatch_ref"`' in errors


def test_merged_pr_main_releasability_dispatcher_rejects_unguarded_lookup() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        IMMUTABLE_REF_LOOKUP_CONDITION,
        'existing_ref_sha="$(gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$dispatch_ref" --jq .object.sha 2>/dev/null)"',
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must use the complete immutable-ref lookup "
        "condition ending immediately in `; then`"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_lookup_condition_suffix() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        IMMUTABLE_REF_LOOKUP_CONDITION,
        IMMUTABLE_REF_LOOKUP_CONDITION.replace("; then", " && false; then"),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must use the complete immutable-ref lookup "
        "condition ending immediately in `; then`"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_trailing_reset_command() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        LOOKUP_FAILURE_RESET_BLOCK,
        (
            '\n          else\n            existing_ref_sha=""\n'
            '            gh api "repos/$GITHUB_REPOSITORY/actions/runs?per_page=1" >/dev/null\n'
            "          fi\n"
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml lookup failure arm must only reset "
        "`existing_ref_sha` before the outer `fi`"
    ) in errors


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
