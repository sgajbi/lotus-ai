"""Routing and capability posture read-model contracts (issue #244 S5, #176 S4).

Split from contracts/providers.py when the module budget fired (issue #295,
S2): the posture read models are a cohesive operator-surface family consumed
by the routing-posture service and its route, not by the execution path.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.capability_requirements import CapabilityRequirements

from app.contracts.providers import (
    ProviderDegradationStatusDescriptor,
    CandidateUniverse,
    ProviderFailureCategory,
    RoutingStrategy,
)


class CapabilityPostureCandidateDescriptor(BaseModel):
    """One universe candidate's capability eligibility for queried requirements."""

    entry_id: str = Field(min_length=1, description="Catalogue entry assessed.")
    eligible: bool = Field(description="Whether the entry satisfies the queried requirements.")
    rejection_reason: ProviderFailureCategory | None = Field(
        default=None,
        description=(
            "Bounded category when ineligible (CAPABILITY_NOT_SUPPORTED, "
            "CAPABILITY_UNKNOWN or CAPABILITY_DEGRADED); null when eligible."
        ),
    )
    detail: str | None = Field(
        default=None, description="Human-readable account of the ineligibility; null otherwise."
    )


class CapabilityPostureDescriptor(BaseModel):
    """Who is eligible for queried capability requirements, and who would serve.

    The answer to the operator question "for capability X: who is eligible,
    who is excluded and why, who would be selected" (issue #244, S5) -
    computed with the exact eligibility check the gateway enforces, over the
    exact universe it would enumerate.
    """

    requirements: CapabilityRequirements = Field(description="The requirements queried.")
    candidates: list[CapabilityPostureCandidateDescriptor] = Field(
        description="Every universe candidate in policy order with its verdict.",
    )
    would_select_entry_id: str | None = Field(
        default=None,
        description=(
            "First eligible candidate in policy order - what the next execution with "
            "these requirements would bind, health permitting; null when none is eligible."
        ),
    )


class RoutingPostureCandidateDescriptor(BaseModel):
    provider_id: str | None = Field(
        default=None,
        description="Configured live provider identity; null when no live identity is set.",
    )
    provider_mode: str = Field(description="Configured provider execution mode.")
    model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed catalogue entry the live identity resolves to, when configured.",
    )
    model_family: str | None = Field(default=None, description="Model family of the candidate.")
    model_revision: str | None = Field(
        default=None, description="Exact (or fallback) revision of the candidate."
    )
    revision_pinned: bool | None = Field(
        default=None, description="Whether the catalogue entry pins an exact revision."
    )
    lifecycle_state: str | None = Field(
        default=None, description="Lifecycle state of the catalogue entry."
    )


class ConnectionIdentityDescriptor(BaseModel):
    """One governed identity's resolved connection facts (issue #303).

    Answers the operator identity questions - which provider, which model
    revision, which deployment, which region posture, which credential
    reference - from the SAME merged connection-material map execution
    resolves through (issue #298), so inspection and execution can never
    disagree. The credential is a reference name only; the secret never
    appears on any read surface.
    """

    entry_id: str = Field(min_length=1, description="Catalogue identity of the candidate.")
    provider_id: str = Field(min_length=1, description="Provider this identity serves through.")
    model_revision: str = Field(
        min_length=1, description="Model revision (or model id when unversioned)."
    )
    deployment: str | None = Field(
        default=None,
        description="Hosting deployment identity; null for direct provider APIs.",
    )
    region: str | None = Field(
        default=None,
        description=(
            "Informational residency posture declared on the connection material; "
            "never an eligibility gate until a governed residency requirement exists."
        ),
    )
    endpoint_host: str | None = Field(
        default=None,
        description="Host portion of the connection endpoint; never the full URL.",
    )
    credential_env: str | None = Field(
        default=None,
        description=(
            "Name of the environment variable referenced for the credential; null for "
            "seeded identities (settings-supplied credential) or keyless endpoints."
        ),
    )
    seeded: bool = Field(
        description=(
            "True when the connection facts come from the legacy settings pair; false "
            "for declared connection material."
        ),
    )


class RoutingPostureResponse(BaseModel):
    service: str = Field(description="Service name emitting the routing posture.")
    version: str = Field(description="Current lotus-ai service version.")
    policy_id: str = Field(description="Routing policy currently in force.")
    policy_version: str = Field(description="Version of the routing policy.")
    strategy: RoutingStrategy = Field(description="Routing strategy the policy applies.")
    candidate: RoutingPostureCandidateDescriptor = Field(
        description="The primary candidate the policy would consider first right now.",
    )
    degradation: "ProviderDegradationStatusDescriptor" = Field(
        description="Current circuit-breaker posture for the primary candidate.",
    )
    fallback_candidate: RoutingPostureCandidateDescriptor | None = Field(
        default=None,
        description=(
            "The configured alternate candidate under the ordered-fallback strategy; "
            "null under the fixed strategy or when no alternate identity is configured."
        ),
    )
    fallback_degradation: "ProviderDegradationStatusDescriptor | None" = Field(
        default=None,
        description=(
            "Circuit-breaker posture for the alternate candidate, keyed to its provider "
            "identity; null whenever fallback_candidate is null."
        ),
    )
    quota_enforced: bool = Field(description="Whether live-text quota enforcement is on.")
    budget_enforced: bool = Field(description="Whether live-text budget enforcement is on.")
    enforcing_kill_switch_count: int = Field(
        ge=0,
        description="Currently enforcing kill-switch activations (any scope).",
    )
    candidate_universe: CandidateUniverse | None = Field(
        default=None,
        description=(
            "The derived candidate universe the next ordered execution would enumerate - "
            "the same derivation the gateway consumes, so this posture can never disagree "
            "with what routing would actually do (issue #244, U3). Null under the fixed "
            "strategy, which does not enumerate a universe."
        ),
    )
    capability_posture: CapabilityPostureDescriptor | None = Field(
        default=None,
        description=(
            "Per-candidate capability eligibility for the queried requirements (issue "
            "#244, S5): who is eligible, who is excluded and why, and who would be "
            "selected first. Present only when requirements were queried under the "
            "ordered strategy."
        ),
    )
    connection_identities: list[ConnectionIdentityDescriptor] = Field(
        default_factory=list,
        description=(
            "Every governed identity's resolved connection facts (issue #303), from the "
            "same merged material map execution resolves through - provider, revision, "
            "deployment, region posture and credential reference name per identity."
        ),
    )
    notes: list[str] = Field(description="Boundary statements this posture ships with.")
