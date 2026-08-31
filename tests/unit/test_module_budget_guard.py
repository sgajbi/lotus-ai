"""The module budget is a ratchet, not a band (issue #154, S3).

Both rules exist because the 30-module readiness duplication and the
four >1,000-line modules grew one accepted exception at a time. The guard
fails on growth, refuses new copy-paste readiness modules, and - the part
that keeps a ratchet honest - fails when a recorded ceiling is now higher
than reality, so shrinking must be banked rather than leaving headroom.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_module_budget as budget  # type: ignore[import-not-found]  # noqa: E402


def test_the_repository_currently_satisfies_its_budget() -> None:
    assert budget.module_budget_violations() == []
    assert budget.readiness_module_violations() == []


def test_a_module_over_its_ceiling_is_a_violation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(budget, "DEFAULT_MAX_LINES", 10)
    monkeypatch.setattr(budget, "OVERSIZED_ALLOWLIST", {})
    violations = budget.module_budget_violations()
    assert violations
    assert any("exceeds its budget" in violation for violation in violations)


def test_a_ceiling_above_reality_must_be_lowered(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(budget, "OVERSIZED_ALLOWLIST", {"services/readiness_catalog.py": 100_000})
    violations = budget.module_budget_violations()
    assert any("lower its allowlist ceiling" in violation for violation in violations)


def test_a_stale_allowlist_entry_is_a_violation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(budget, "OVERSIZED_ALLOWLIST", {"services/deleted_module.py": 1200})
    assert any(
        "allowlisted but missing" in violation for violation in budget.module_budget_violations()
    )


def test_a_new_readiness_module_is_refused(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(budget, "ALLOWED_READINESS_MODULES", frozenset())
    violations = budget.readiness_module_violations()
    assert violations
    assert any("new readiness modules are not accepted" in violation for violation in violations)


def test_the_deleted_runbook_family_stays_deleted() -> None:
    """S1 replaced ten copy-paste runbook modules with one catalog; none of
    them may reappear without failing this guard."""

    deleted = {
        "artifact_runbook_readiness.py",
        "access_control_runbook_readiness.py",
        "production_baseline_runbook_readiness.py",
        "deployment_split_runbook_readiness.py",
        "prompt_runbook_readiness.py",
        "observability_runbook_readiness.py",
        "resilience_runbook_readiness.py",
        "first_use_case_runbook_readiness.py",
        "safety_runbook_readiness.py",
        "retrieval_runbook_readiness.py",
    }
    assert deleted.isdisjoint(budget.ALLOWED_READINESS_MODULES)
    services = budget.SOURCE_ROOT / "services"
    assert not [name for name in deleted if (services / name).is_file()]
