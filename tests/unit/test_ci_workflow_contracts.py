from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
IMMUTABLE_REF_LOOKUP_CONDITIONS = (
    (
        'if existing_ref_sha="$(gh api '
        '"repos/$GITHUB_REPOSITORY/git/ref/tags/$dispatch_ref" '
        '--jq .object.sha 2>/dev/null)"; then'
    ),
    (
        'if existing_ref_sha="$(gh api '
        '"repos/$GITHUB_REPOSITORY/git/ref/tags/${dispatch_ref}" '
        '--jq .object.sha 2>/dev/null)"; then'
    ),
)
IMMUTABLE_REF_LOOKUP_CONDITION = IMMUTABLE_REF_LOOKUP_CONDITIONS[0]
IMMUTABLE_REF_MISMATCH_CONDITION = 'if [ "$existing_ref_sha" != "$MERGE_COMMIT_SHA" ]; then'
IMMUTABLE_REF_CREATION_CONDITION = 'if [ -z "$existing_ref_sha" ]; then'
IMMUTABLE_REF_CREATION_COMMAND = 'gh api "repos/$GITHUB_REPOSITORY/git/refs"'


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
    if not _has_conditionally_guarded_immutable_ref_lookup(text):
        errors.append(
            "merged-pr-main-releasability.yml must guard immutable-ref lookup "
            "with an if/else reset before dispatch"
        )
    elif not _guarded_lookup_success_arms_fail_on_ref_mismatch(text):
        errors.append(
            "merged-pr-main-releasability.yml must fail closed with exit 1 when "
            "an existing immutable dispatch ref points to a different SHA"
        )
    if any("||" in block for block in _immutable_ref_lookup_blocks(text)):
        errors.append(
            "merged-pr-main-releasability.yml must not mask immutable-ref lookup "
            "failures with shell OR fallbacks"
        )
    if not _conditionally_creates_absent_immutable_ref(text):
        errors.append(
            "merged-pr-main-releasability.yml must create the immutable dispatch ref only "
            "inside the empty existing-ref branch"
        )
    return errors


def _opens_nested_shell_scope(stripped_line: str) -> bool:
    return (
        stripped_line == "("
        or stripped_line.startswith("(")
        or stripped_line.startswith(("if ", "for ", "while ", "until ", "case "))
        or stripped_line.startswith("function ")
        or stripped_line.endswith("() {")
        or stripped_line.endswith("(){")
        or stripped_line.endswith(" {")
    )


def _closes_nested_shell_scope(stripped_line: str) -> bool:
    return stripped_line in {"fi", "done", "esac", "}"} or stripped_line.startswith(")")


def _is_shell_comment(stripped_line: str) -> bool:
    return stripped_line.startswith("#")


def _contains_immutable_dispatch_ref_lookup(text: str) -> bool:
    return "git/ref/tags/$dispatch_ref" in text or "git/ref/tags/${dispatch_ref}" in text


def _immutable_ref_lookup_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        stripped_line = line.strip()
        if _is_shell_comment(stripped_line) or not _contains_immutable_dispatch_ref_lookup(line):
            continue

        block_lines = [line]
        if (
            stripped_line == "then"
            or stripped_line.endswith("; then")
            or stripped_line.endswith(')"')
        ):
            blocks.append("\n".join(block_lines))
            continue
        for follow in lines[index + 1 :]:
            block_lines.append(follow)
            stripped = follow.strip()
            if stripped == "then" or stripped.endswith("; then"):
                break
            if not follow.rstrip().endswith("\\") and stripped.endswith(')"'):
                break
        blocks.append("\n".join(block_lines))
    return blocks


def _immutable_ref_lookup_guard_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line not in IMMUTABLE_REF_LOOKUP_CONDITIONS:
            continue

        block_lines = [line]
        depth = 1
        for follow in lines[index + 1 :]:
            block_lines.append(follow)
            stripped_follow = follow.strip()
            if _opens_nested_shell_scope(stripped_follow):
                depth += 1
            if _closes_nested_shell_scope(stripped_follow):
                depth -= 1
            if depth == 0:
                break
        blocks.append("\n".join(block_lines))
    return blocks


def _outer_lookup_else_arm_has_unconditional_reset(block: str) -> bool:
    lines = block.splitlines()
    else_index: int | None = None
    depth = 1
    for index, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "else" and depth == 1:
            else_index = index
            break
        if _opens_nested_shell_scope(stripped):
            depth += 1
        if _closes_nested_shell_scope(stripped):
            depth -= 1

    if else_index is None:
        return False

    executable_commands: list[str] = []
    depth = 1
    for line in lines[else_index + 1 :]:
        stripped = line.strip()
        if stripped == "fi" and depth == 1:
            break
        if not stripped or _is_shell_comment(stripped):
            continue
        executable_commands.append(stripped)
        if _opens_nested_shell_scope(stripped):
            depth += 1
        if _closes_nested_shell_scope(stripped):
            depth -= 1
    return executable_commands == ['existing_ref_sha=""']


def _outer_lookup_then_arm_has_mismatch_exit(block: str) -> bool:
    lines = block.splitlines()
    then_arm: list[str] = []
    depth = 1
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "else" and depth == 1:
            break
        then_arm.append(line)
        if _opens_nested_shell_scope(stripped):
            depth += 1
        if _closes_nested_shell_scope(stripped):
            depth -= 1

    condition_depth = 1
    for index, line in enumerate(then_arm):
        stripped_line = line.strip()
        if stripped_line != IMMUTABLE_REF_MISMATCH_CONDITION or condition_depth != 1:
            if _opens_nested_shell_scope(stripped_line):
                condition_depth += 1
            if _closes_nested_shell_scope(stripped_line):
                condition_depth -= 1
            continue

        direct_executable_commands: list[str] = []
        depth = 1
        for follow in then_arm[index + 1 :]:
            stripped_follow = follow.strip()
            if stripped_follow == "fi" and depth == 1:
                break
            if not stripped_follow or _is_shell_comment(stripped_follow):
                continue
            if depth == 1:
                direct_executable_commands.append(stripped_follow)
            if _opens_nested_shell_scope(stripped_follow):
                depth += 1
            if _closes_nested_shell_scope(stripped_follow):
                depth -= 1
        return "exit 1" in direct_executable_commands
    return False


def _is_conditionally_guarded_immutable_ref_lookup_block(block: str) -> bool:
    return (
        _contains_immutable_dispatch_ref_lookup(block)
        and "\n" in block
        and "else" in block
        and _outer_lookup_else_arm_has_unconditional_reset(block)
        and block.strip().endswith("fi")
    )


def _has_conditionally_guarded_immutable_ref_lookup(text: str) -> bool:
    lookup_blocks = _immutable_ref_lookup_blocks(text)
    guarded_blocks = _immutable_ref_lookup_guard_blocks(text)
    return (
        bool(lookup_blocks)
        and len(lookup_blocks) == len(guarded_blocks)
        and all(
            _is_conditionally_guarded_immutable_ref_lookup_block(block) for block in guarded_blocks
        )
    )


def _guarded_lookup_success_arms_fail_on_ref_mismatch(text: str) -> bool:
    guarded_blocks = _immutable_ref_lookup_guard_blocks(text)
    return bool(guarded_blocks) and all(
        _outer_lookup_then_arm_has_mismatch_exit(block) for block in guarded_blocks
    )


def _conditionally_creates_absent_immutable_ref(text: str) -> bool:
    lines = text.splitlines()
    depth = 0
    for index, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line == IMMUTABLE_REF_CREATION_CONDITION and depth == 0:
            direct_executable_commands: list[str] = []
            creation_depth = 1
            for follow in lines[index + 1 :]:
                stripped_follow = follow.strip()
                if stripped_follow == "fi" and creation_depth == 1:
                    break
                if not stripped_follow or _is_shell_comment(stripped_follow):
                    continue
                if creation_depth == 1:
                    direct_executable_commands.append(stripped_follow)
                if _opens_nested_shell_scope(stripped_follow):
                    creation_depth += 1
                if _closes_nested_shell_scope(stripped_follow):
                    creation_depth -= 1
            return any(
                command == IMMUTABLE_REF_CREATION_COMMAND
                or command.startswith(f"{IMMUTABLE_REF_CREATION_COMMAND} ")
                for command in direct_executable_commands
            )
        if not stripped_line or _is_shell_comment(stripped_line):
            continue
        if _opens_nested_shell_scope(stripped_line):
            depth += 1
        if _closes_nested_shell_scope(stripped_line):
            depth -= 1
    return False


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
        "merged-pr-main-releasability.yml must guard immutable-ref lookup "
        "with an if/else reset before dispatch"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_accepts_braced_lookup() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        "git/ref/tags/$dispatch_ref",
        "git/ref/tags/${dispatch_ref}",
    )

    assert _merged_pr_dispatch_contract_errors(text) == []


def test_merged_pr_main_releasability_dispatcher_ignores_commented_lookup() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        IMMUTABLE_REF_LOOKUP_CONDITION,
        (
            "          # Lookup repos/$GITHUB_REPOSITORY/git/ref/tags/$dispatch_ref "
            "before creating it.\n"
            f"          {IMMUTABLE_REF_LOOKUP_CONDITION}"
        ),
    )

    assert _merged_pr_dispatch_contract_errors(text) == []


def test_merged_pr_main_releasability_dispatcher_rejects_later_braced_unguarded_lookup() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        '          if [ -z "$existing_ref_sha" ]; then',
        (
            '          existing_ref_sha="$(gh api '
            '"repos/$GITHUB_REPOSITORY/git/ref/tags/${dispatch_ref}" '
            '--jq .object.sha 2>/dev/null)"\n'
            '          if [ -z "$existing_ref_sha" ]; then'
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must guard immutable-ref lookup "
        "with an if/else reset before dispatch"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_masked_lookup_fallback() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        IMMUTABLE_REF_LOOKUP_CONDITION,
        (
            'existing_ref_sha="$(gh api '
            '"repos/$GITHUB_REPOSITORY/git/ref/tags/$dispatch_ref" '
            '--jq .object.sha 2>/dev/null || :)"'
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must not mask immutable-ref lookup "
        "failures with shell OR fallbacks"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_lookup_condition_suffix() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        IMMUTABLE_REF_LOOKUP_CONDITION,
        IMMUTABLE_REF_LOOKUP_CONDITION.replace("; then", " && false; then"),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must guard immutable-ref lookup "
        "with an if/else reset before dispatch"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_trailing_reset_command() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        '\n          else\n            existing_ref_sha=""\n          fi\n',
        (
            '\n          else\n            existing_ref_sha=""\n'
            '            gh api "repos/$GITHUB_REPOSITORY/actions/runs?per_page=1" >/dev/null\n'
            "          fi\n"
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must guard immutable-ref lookup "
        "with an if/else reset before dispatch"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_non_failing_mismatch_branch() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace("              exit 1", "              :")

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must fail closed with exit 1 when "
        "an existing immutable dispatch ref points to a different SHA"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_function_scoped_mismatch_exit() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        "              exit 1",
        "              collision_failure() {\n                exit 1\n              }",
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must fail closed with exit 1 when "
        "an existing immutable dispatch ref points to a different SHA"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_nested_mismatch_condition() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        (
            '            if [ "$existing_ref_sha" != "$MERGE_COMMIT_SHA" ]; then\n'
            '              echo "::error::Dispatch ref $dispatch_ref points to '
            '$existing_ref_sha, expected $MERGE_COMMIT_SHA"\n'
            "              exit 1\n"
            "            fi"
        ),
        (
            "            if false; then\n"
            '              if [ "$existing_ref_sha" != "$MERGE_COMMIT_SHA" ]; then\n'
            '                echo "::error::Dispatch ref $dispatch_ref points to '
            '$existing_ref_sha, expected $MERGE_COMMIT_SHA"\n'
            "                exit 1\n"
            "              fi\n"
            "            fi"
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must fail closed with exit 1 when "
        "an existing immutable dispatch ref points to a different SHA"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_subshell_masked_mismatch_exit() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        (
            '            if [ "$existing_ref_sha" != "$MERGE_COMMIT_SHA" ]; then\n'
            '              echo "::error::Dispatch ref $dispatch_ref points to '
            '$existing_ref_sha, expected $MERGE_COMMIT_SHA"\n'
            "              exit 1\n"
            "            fi"
        ),
        (
            "            (\n"
            '              if [ "$existing_ref_sha" != "$MERGE_COMMIT_SHA" ]; then\n'
            '                echo "::error::Dispatch ref $dispatch_ref points to '
            '$existing_ref_sha, expected $MERGE_COMMIT_SHA"\n'
            "                exit 1\n"
            "              fi\n"
            "            ) || true"
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must fail closed with exit 1 when "
        "an existing immutable dispatch ref points to a different SHA"
    ) in errors


def test_merged_pr_main_releasability_dispatcher_rejects_unconditional_ref_creation() -> None:
    workflow = WORKFLOW_DIR / "merged-pr-main-releasability.yml"
    text = workflow.read_text(encoding="utf-8").replace(
        (
            '          if [ -z "$existing_ref_sha" ]; then\n'
            '            gh api "repos/$GITHUB_REPOSITORY/git/refs" \\\n'
            '              -f ref="refs/tags/$dispatch_ref" \\\n'
            '              -f sha="$MERGE_COMMIT_SHA" >/dev/null\n'
            "          fi"
        ),
        (
            '          gh api "repos/$GITHUB_REPOSITORY/git/refs" \\\n'
            '            -f ref="refs/tags/$dispatch_ref" \\\n'
            '            -f sha="$MERGE_COMMIT_SHA" >/dev/null'
        ),
    )

    errors = _merged_pr_dispatch_contract_errors(text)

    assert (
        "merged-pr-main-releasability.yml must create the immutable dispatch ref only "
        "inside the empty existing-ref branch"
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
