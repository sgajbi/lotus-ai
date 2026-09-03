"""Architecture guard for the internal all-tenant audit scope (issues #168/#159).

The internal aggregate scope is an authorization bypass by construction: any
module that reads audit records with it serves all-tenant data regardless of
caller policy. This guard pins the EXACT set of modules allowed to reference
it, so a new public request path cannot quietly inherit all-tenant access by
convention - adding or removing a consumer must edit this allowlist in the
same change that justifies it.

The five allowed service consumers were classified on issue #159: their
response contracts aggregate by task, capability, and platform caller only and
carry no tenant identifiers. `observability_breakdowns` is deliberately NOT in
the set - its tenant dimension is the feature, and it reads with the caller's
resolved scope instead.
"""

from __future__ import annotations

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"

ALLOWED_REFERENCING_MODULES = {
    "contracts/audit_access.py",  # the definition itself
    "services/app_capability_rollout_observability.py",
    "services/capability_pack_observability.py",
    # The lifecycle engine must see every tenant's rows to expire them
    # (issue #158, S2a; classified on #159): not a request path - no caller,
    # no response contract - and every deletion it performs is evidenced on
    # the append-only data_lifecycle_events ledger.
    "services/data_lifecycle_engine.py",
    "services/task_execution_evidence_summary.py",
    "services/task_execution_summary.py",
    "services/task_retrieval_execution_summary.py",
}


def test_internal_aggregate_audit_scope_is_referenced_only_by_the_classified_set() -> None:
    referencing = {
        path.relative_to(SRC_ROOT).as_posix()
        for path in SRC_ROOT.rglob("*.py")
        if "INTERNAL_AGGREGATE_AUDIT_SCOPE" in path.read_text(encoding="utf-8")
    }
    assert referencing == ALLOWED_REFERENCING_MODULES, (
        "INTERNAL_AGGREGATE_AUDIT_SCOPE consumers changed. Every consumer serves "
        "all-tenant audit data with no caller check: a NEW consumer must be classified "
        "as identifier-free on issue #159 (or use resolve_audit_read_scope instead) "
        "before joining this allowlist; a REMOVED one must leave it."
    )
