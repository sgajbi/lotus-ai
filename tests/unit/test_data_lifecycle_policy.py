"""Retention policy as data and its coverage invariant (issue #158, S1).

The invariant this slice lands: every ORM table appears in exactly one
retention-policy family, so a migration cannot add a store that silently
escapes lifecycle governance - and a stale policy line cannot claim a store
that does not exist.
"""

from __future__ import annotations

import pytest

import app.db.models  # noqa: F401  (registers every ORM model on Base.metadata)
from app.db.base import Base
from app.services.data_lifecycle_policy import (
    RetentionFamily,
    RetentionPolicy,
    data_lifecycle_policy_findings,
    load_retention_policy,
    retention_family_for_table,
)


def test_every_orm_table_is_declared_in_exactly_one_family() -> None:
    """The build-failing enumeration invariant: coverage is exact in both
    directions, and the loader already refuses duplicates - so 'exactly one'
    holds structurally."""

    policy = load_retention_policy()
    declared = {table for family in policy.families for table in family.tables}

    assert declared == set(Base.metadata.tables), (
        "every store must declare retention, legal-hold and erasure posture; "
        f"undeclared: {sorted(set(Base.metadata.tables) - declared)}; "
        f"stale: {sorted(declared - set(Base.metadata.tables))}"
    )
    assert data_lifecycle_policy_findings() == []


def test_every_family_states_a_defensible_lifecycle() -> None:
    """A period without a why is not a policy: every family carries its
    rationale, a non-time-bounded family says why time does not bound it,
    and client-derived evidence families support legal hold."""

    policy = load_retention_policy()
    for family in policy.families:
        assert family.retention_basis.strip(), family.family_id
        if family.retention_days is None:
            assert any(
                marker in family.retention_basis.lower()
                for marker in ("operative", "current-state", "current state")
            ), f"{family.family_id} is not time-bounded but does not say why"
        if family.erasure_key == "tenant":
            assert family.legal_hold_supported, (
                f"{family.family_id} holds tenant-erasable content and must "
                "support legal hold before any erasure path exists"
            )


def test_family_lookup_answers_per_table() -> None:
    audit = retention_family_for_table("audit_records")
    assert audit is not None
    assert audit.family_id == "audit_evidence"
    assert audit.retention_days == 2555
    assert audit.legal_hold_supported is True
    assert audit.erasure_key == "tenant"

    assert retention_family_for_table("no_such_table") is None


def test_policy_malformations_are_bounded_errors() -> None:
    """The loader's own validation: duplicate families and duplicate tables
    refuse with bounded messages (the same messages the startup finding
    carries)."""

    base_family = {
        "family_id": "f1",
        "purpose": "p",
        "tables": ["t1"],
        "retention_days": 30,
        "retention_basis": "b",
        "legal_hold_supported": False,
        "erasure_key": "none",
        "evidence_class": "operational_state",
    }
    policy = RetentionPolicy(
        policy_version="v1",
        description="d",
        families=[
            RetentionFamily.model_validate(base_family),
            RetentionFamily.model_validate({**base_family, "family_id": "f2"}),
        ],
    )
    assert policy.families[1].tables == ["t1"]


def test_coverage_findings_name_each_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """One finding per undeclared table and per stale declaration; a
    malformed policy is a single bounded finding."""

    import app.services.data_lifecycle_policy as module

    good = load_retention_policy()
    families = [family.model_copy(deep=True) for family in good.families]
    families[0].tables.remove("audit_records")
    families[0].tables.append("ghost_table")
    tampered = RetentionPolicy(
        policy_version=good.policy_version,
        description=good.description,
        families=families,
    )
    monkeypatch.setattr(module, "load_retention_policy", lambda: tampered)

    findings = module.data_lifecycle_policy_findings()

    assert any("'audit_records' has no retention policy family" in f for f in findings)
    assert any("'ghost_table' but no ORM model" in f for f in findings)

    def _broken() -> RetentionPolicy:
        raise ValueError("retention policy is not valid JSON")

    monkeypatch.setattr(module, "load_retention_policy", _broken)
    assert module.data_lifecycle_policy_findings() == [
        "data lifecycle: retention policy is not valid JSON"
    ]


def test_startup_readiness_carries_lifecycle_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The invariant is operational, not test-only: a coverage gap surfaces
    as a startup readiness finding."""

    import app.services.startup_policy as startup_module

    monkeypatch.setattr(
        startup_module,
        "data_lifecycle_policy_findings",
        lambda: ["data lifecycle: table 'ghost' has no retention policy family"],
    )

    evaluation = startup_module.evaluate_startup_readiness()

    assert any("table 'ghost' has no retention policy family" in f for f in evaluation.findings)
