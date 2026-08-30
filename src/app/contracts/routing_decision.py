"""Explainable routing decisions (issue #176, slice 1).

Every AI execution records exactly one routing decision: which policy decided,
which candidates were considered, what was selected and why, and when. The
record exists from the very first, single-candidate `fixed` strategy onward -
consumers, operators and audits build on the record, and later slices grow it
additively (candidate rejections with bounded reasons arrive with the
eligibility composition that actually produces them; fallback paths arrive
with the fallback strategy).

Slice 1 deliberately contains no vocabulary this slice cannot produce.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ROUTING_POLICY_FIXED_CONFIGURED_MODE = "fixed_configured_mode"
ROUTING_POLICY_VERSION_V1 = "v1"


class RoutingStrategy(str, Enum):
    FIXED = "FIXED"


class RoutingCandidateDescriptor(BaseModel):
    """One execution target the routing policy considered."""

    provider_id: str = Field(description="Provider identity of the candidate.")
    provider_mode: str = Field(description="Execution mode the candidate serves.")
    model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed catalogue entry for the candidate, on live paths.",
    )
    model_revision: str | None = Field(
        default=None,
        description="Exact (or fallback) model revision of the candidate when known.",
    )


class RoutingDecisionDescriptor(BaseModel):
    """The recorded rationale for one execution's provider/model selection."""

    policy_id: str = Field(description="Routing policy that made this decision.")
    policy_version: str = Field(description="Version of the routing policy.")
    strategy: RoutingStrategy = Field(description="Routing strategy the policy applied.")
    candidates: list[RoutingCandidateDescriptor] = Field(
        description="Every candidate the policy considered for this execution.",
    )
    selected_provider_id: str = Field(
        description="Provider identity the execution was routed to.",
    )
    selected_model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed catalogue entry the execution was routed to, on live paths.",
    )
    decided_at: str = Field(description="Instant the routing decision was made (UTC).")
    selection_reason: str = Field(
        description="Human-readable statement of why the selected candidate won.",
    )
