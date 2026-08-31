"""Deterministic output-validation vocabulary (issue #156, S1).

Every AI output leaving the service carries a validation verdict and an
explicit non-authoritative marking. The vocabulary is bounded: a REJECTED
output is withheld whole; VALIDATION_UNAVAILABLE is the fail-closed state
for a validator fault; UNVALIDATED_LOCAL_ONLY marks a local-profile output
that bypassed a rule promoted profiles enforce.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

AI_OUTPUT_AUTHORITY = "non_authoritative_ai_output"
OUTPUT_VALIDATION_RULESET_VERSION = "output-validation.v3"


class OutputValidationState(str, Enum):
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    UNVALIDATED_LOCAL_ONLY = "UNVALIDATED_LOCAL_ONLY"
    VALIDATION_UNAVAILABLE = "VALIDATION_UNAVAILABLE"


class OutputValidationOutcome(BaseModel):
    """The recorded verdict for one execution's output."""

    validation_state: OutputValidationState = Field(
        description="Deterministic validation verdict for the output."
    )
    authority: str = Field(
        default=AI_OUTPUT_AUTHORITY,
        description="Authority marking: AI output is never authoritative financial truth.",
    )
    ruleset_version: str = Field(
        default=OUTPUT_VALIDATION_RULESET_VERSION,
        description="Version of the validation rule set that produced this verdict.",
    )
    failed_rule_ids: list[str] = Field(
        default_factory=list,
        description="Rule identifiers that rejected the output; empty unless REJECTED.",
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Bounded human-readable statements for each failed or waived rule.",
    )
