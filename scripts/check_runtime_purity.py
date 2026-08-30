"""Production-source purity guard (issue #148).

Fails when production code under src/ imports test tooling (unittest, mock,
pytest) or references pytest's monkeypatch, and when a string literal that
is not a self-describing credential reference is assigned to an api-key
attribute. Production code must never depend on test-harness mechanics, and
credentials must come from configuration or fixtures, never from literals.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_IMPORT_ROOTS = {"unittest", "mock", "pytest"}
ALLOWED_API_KEY_LITERAL_PREFIXES = ("credential-ref:",)


def _is_api_key_target(target: ast.expr) -> bool:
    if isinstance(target, ast.Name):
        return target.id.endswith("api_key")
    if isinstance(target, ast.Attribute):
        return target.attr.endswith("api_key")
    return False


def _violations_for_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{path}:{node.lineno}: test-tooling import '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                violations.append(f"{path}:{node.lineno}: test-tooling import 'from {node.module}'")
        elif isinstance(node, ast.Name) and node.id == "monkeypatch":
            violations.append(f"{path}:{node.lineno}: test-tooling reference 'monkeypatch'")
        elif isinstance(node, ast.arg) and node.arg == "monkeypatch":
            violations.append(f"{path}:{node.lineno}: test-tooling reference 'monkeypatch'")
        elif isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if (
                isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and value.value
                and not value.value.startswith(ALLOWED_API_KEY_LITERAL_PREFIXES)
                and any(_is_api_key_target(target) for target in targets)
            ):
                violations.append(f"{path}:{node.lineno}: secret-shaped api-key literal assignment")
    return violations


def main(root: str = "src") -> int:
    violations: list[str] = []
    for path in sorted(Path(root).rglob("*.py")):
        violations.extend(_violations_for_file(path))
    if violations:
        print("\n".join(violations))
        return 1
    print("Runtime purity guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src"))
