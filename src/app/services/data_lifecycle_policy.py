"""Retention policy as data (issue #158, S1).

Every lotus-ai store family declares its retention period, legal-hold
support, erasure key and evidence class - with the rationale stated - in
``contracts/data-lifecycle/retention-policy.v1.json``. This module loads and
validates it, and holds the coverage invariant: every ORM table appears in
exactly one policy family, so a migration cannot add an undeclared store.
The lifecycle engine that applies the policy is the S2 slice; the invariant
that every store is DECLARED lands first and cannot rot.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

import app.db.models  # noqa: F401  (registers every ORM model on Base.metadata)
from app.db.base import Base

_POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "data-lifecycle"
    / "retention-policy.v1.json"
)


class RetentionFamily(BaseModel):
    """One store family's declared lifecycle."""

    family_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    tables: list[str] = Field(min_length=1)
    retention_days: int | None = Field(
        ge=1,
        description=(
            "Time-bounded retention in days; null means not time-bounded, and the "
            "retention_basis must say why (operative configuration, current state)."
        ),
    )
    retention_basis: str = Field(
        min_length=1,
        description="The stated rationale - a period without a why is not a policy.",
    )
    legal_hold_supported: bool
    erasure_key: Literal["tenant", "request", "subject", "shared_reference", "none"]
    evidence_class: str = Field(min_length=1)
    enforcement: Literal["ENFORCED", "DECLARED_ONLY", "NOT_TIME_BOUNDED"] = Field(
        description=(
            "Whether the lifecycle engine actually applies this family's retention "
            "(issue #158, S2a): ENFORCED means an engine handler deletes past-retention "
            "rows; DECLARED_ONLY says honestly that the period is stated but not yet "
            "applied; NOT_TIME_BOUNDED matches a null retention period."
        ),
    )


class RetentionPolicy(BaseModel):
    policy_version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    families: list[RetentionFamily] = Field(min_length=1)


@lru_cache(maxsize=1)
def load_retention_policy() -> RetentionPolicy:
    """Load and structurally validate the retention policy.

    Raises ``ValueError`` with a bounded message on any malformation, so the
    startup finding and tests report policy problems identically.
    """

    try:
        raw = _POLICY_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"retention policy is not readable at {_POLICY_PATH.name}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("retention policy is not valid JSON") from exc
    try:
        policy = RetentionPolicy.model_validate(parsed)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ValueError(f"retention policy is invalid at {location}: {first['msg']}") from exc

    seen_families: set[str] = set()
    seen_tables: set[str] = set()
    for family in policy.families:
        if family.family_id in seen_families:
            raise ValueError(f"retention policy declares family '{family.family_id}' twice")
        seen_families.add(family.family_id)
        if (family.retention_days is None) != (family.enforcement == "NOT_TIME_BOUNDED"):
            raise ValueError(
                f"retention policy family '{family.family_id}' is inconsistent: a null "
                "retention period and the NOT_TIME_BOUNDED posture must imply each other"
            )
        for table in family.tables:
            if table in seen_tables:
                raise ValueError(
                    f"retention policy declares table '{table}' in more than one family"
                )
            seen_tables.add(table)
    return policy


def retention_family_for_table(table_name: str) -> RetentionFamily | None:
    """The declared family for one ORM table, or None when undeclared."""

    for family in load_retention_policy().families:
        if table_name in family.tables:
            return family
    return None


def data_lifecycle_policy_findings() -> list[str]:
    """The coverage invariant (issue #158, S1), as startup-finding lines.

    A malformed policy is one finding; an ORM table outside the policy - the
    way a new migration silently escapes lifecycle governance - is one finding
    per table, as is a policy table no model backs (a stale declaration is a
    claim without a store).
    """

    try:
        policy = load_retention_policy()
    except ValueError as exc:
        return [f"data lifecycle: {exc}"]

    declared = {table for family in policy.families for table in family.tables}
    actual = set(Base.metadata.tables)
    findings = [
        f"data lifecycle: table '{table}' has no retention policy family; every store "
        "must declare retention, legal-hold and erasure posture"
        for table in sorted(actual - declared)
    ]
    findings.extend(
        f"data lifecycle: retention policy declares table '{table}' but no ORM model "
        "defines it; remove the stale declaration"
        for table in sorted(declared - actual)
    )
    return findings
