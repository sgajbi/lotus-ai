"""Module-size and readiness-shape budget (issue #154, S3).

Two rules, both ratchets rather than bands:

1. No new ``*_readiness.py`` service module. The runbook family is one
   catalog plus one builder; the surviving modules are the genuinely
   computed ones, enumerated below. A new copy-paste readiness module is
   how the 30-module duplication started, so adding one now fails the
   lane.
2. No module grows past its recorded ceiling. The three oversized modules
   carry dated allowlist entries that may only ever shrink; every other
   module is bounded by the default ceiling.

Both lists are ratchets: shrinking a value is always allowed, raising one
is a deliberate edit that shows up in review.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src" / "app"

DEFAULT_MAX_LINES = 1000

# Dated ceilings for modules that were already oversized when the budget
# landed (2026-09-01). These may only shrink - see the module docstring.
OVERSIZED_ALLOWLIST: dict[str, int] = {
    "services/eval_runtime_execution.py": 1471,
    "services/workflow_pack_registry_seed.py": 1365,
    "routers/workflow_packs.py": 1250,
}

# The readiness modules that survive because they genuinely compute from
# runtime state or serve as shared infrastructure (issue #154, S1/S2).
ALLOWED_READINESS_MODULES = frozenset(
    {
        "access_control_activation_readiness.py",
        "artifact_activation_readiness.py",
        "capability_pack_activation_readiness.py",
        "capability_pack_runbook_readiness.py",
        "deployment_split_activation_readiness.py",
        "first_use_case_readiness.py",
        "governance_readiness.py",
        "observability_activation_readiness.py",
        "production_baseline_activation_readiness.py",
        "production_go_live_activation_readiness.py",
        "production_go_live_runbook_readiness.py",
        "prompt_activation_readiness.py",
        "prompt_evidence_readiness.py",
        "provider_activation_readiness.py",
        "provider_evidence_readiness.py",
        "provider_runbook_readiness.py",
        "resilience_activation_readiness.py",
        "retrieval_activation_readiness.py",
        "retrieval_evidence_readiness.py",
        "runtime_readiness.py",
        "safety_evidence_readiness.py",
    }
)


def _relative(path: Path) -> str:
    return path.relative_to(SOURCE_ROOT).as_posix()


def module_budget_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = _relative(path)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        ceiling = OVERSIZED_ALLOWLIST.get(relative, DEFAULT_MAX_LINES)
        if line_count > ceiling:
            violations.append(f"{relative}: {line_count} lines exceeds its budget of {ceiling}")
    for relative, ceiling in sorted(OVERSIZED_ALLOWLIST.items()):
        path = SOURCE_ROOT / relative
        if not path.is_file():
            violations.append(f"{relative}: allowlisted but missing - remove the stale entry")
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count < ceiling:
            violations.append(
                f"{relative}: now {line_count} lines - lower its allowlist ceiling from "
                f"{ceiling} so the ratchet holds"
            )
    return violations


def readiness_module_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted((SOURCE_ROOT / "services").glob("*_readiness.py")):
        if path.name not in ALLOWED_READINESS_MODULES:
            violations.append(
                f"services/{path.name}: new readiness modules are not accepted - declare the "
                "items in contracts/readiness/runbook_readiness_catalog.json and build them "
                "with services/readiness_catalog.py, or add a computed module to the "
                "allowlist with its reason"
            )
    for name in sorted(ALLOWED_READINESS_MODULES):
        if not (SOURCE_ROOT / "services" / name).is_file():
            violations.append(f"services/{name}: allowlisted but missing - remove the stale entry")
    return violations


def main() -> int:
    violations = module_budget_violations() + readiness_module_violations()
    for violation in violations:
        print(f"module budget violation: {violation}")
    if violations:
        return 1
    print("Module budget guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
