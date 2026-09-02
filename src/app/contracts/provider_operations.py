"""Provider-operations control-plane contracts (issues #152, #157).

Split from ``contracts/providers.py`` when the module-budget ratchet fired:
the reset-control vocabulary is its own governed surface, and every reset is a
permissive action carried by the governed-action primitive.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.governed_actions import GovernedActionRecord
from app.contracts.providers import ProviderQuotaScope


class ProviderOperationsControlActionType(str, Enum):
    RESET_ALL_QUOTAS = "RESET_ALL_QUOTAS"
    RESET_QUOTA_SCOPE = "RESET_QUOTA_SCOPE"
    RESET_BUDGET = "RESET_BUDGET"
    RESET_DEGRADATION = "RESET_DEGRADATION"
    RESET_ALL_PROVIDER_OPERATIONS = "RESET_ALL_PROVIDER_OPERATIONS"


class ProviderOperationsResetIntentRequest(BaseModel):
    """Step one of a governed reset: a verified requester states the intent.

    Every reset action is permissive - it re-opens a spending envelope or
    resumes traffic past the breaker's health protection - so all of them are
    governed (issue #157). Caller identity comes from the authenticated
    credential, never from the body.
    """

    action_type: ProviderOperationsControlActionType = Field(
        description="Requested provider-operations reset action."
    )
    scope: ProviderQuotaScope | None = Field(
        default=None,
        description="Quota scope targeted by the action when resetting one quota scope.",
    )
    scope_key: str | None = Field(
        default=None,
        description="Quota scope key targeted by the action when resetting one quota scope.",
    )
    reason: str = Field(min_length=1, description="Why this reset should happen.")
    requested_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class ProviderOperationsResetApprovalRequest(BaseModel):
    """Step two: a distinct verified credential approves the exact pending reset.

    The approver restates the action type (and scope for targeted quota
    resets) so an approval cannot be redirected to a different reset shape.
    """

    action_type: ProviderOperationsControlActionType = Field(
        description="The reset action being approved; must match the pending action."
    )
    scope: ProviderQuotaScope | None = Field(default=None)
    scope_key: str | None = Field(default=None)
    action_id: str = Field(min_length=1, max_length=64, description="Pending governed action id.")
    action_hash: str = Field(
        min_length=64,
        max_length=64,
        description="Hash of the action being approved, exactly as returned by the request step.",
    )
    approved_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class ProviderOperationsResetApprovalResponse(BaseModel):
    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured provider mode at execution time.")
    event: ProviderOperationsControlEventDescriptor = Field(
        description="Durable provider-operations event recorded for the executed reset."
    )
    governed_action: GovernedActionRecord = Field(
        description="The executed governed-action evidence linking request, approval and reset.",
    )
    summary: list[str] = Field(description="Human-readable statements about the action.")


class ProviderOperationsControlEventDescriptor(BaseModel):
    event_id: str = Field(
        description="Stable identifier for the recorded provider-operations action."
    )
    action_type: ProviderOperationsControlActionType = Field(
        description="Type of provider-operations control action that was recorded."
    )
    scope: ProviderQuotaScope | None = Field(
        default=None,
        description="Quota scope targeted by the action when the action resets a specific quota scope.",
    )
    scope_key: str | None = Field(
        default=None,
        description="Scope key targeted by the action when applicable.",
    )
    reason: str = Field(description="Operator-provided reason for the provider-operations action.")
    requested_by: str = Field(description="Operator or system identity that requested the action.")
    approved_by: str = Field(description="Approver identity recorded for the action.")
    affected_record_count: int = Field(
        description="Number of provider-operations state records affected by the action."
    )
    authorization: AuthorizationDecision = Field(
        description="Typed caller-authorization decision recorded for the provider control action."
    )
    recorded_at: str = Field(description="Timestamp when the action was recorded.")


class ProviderOperationsControlHistoryResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the provider-operations control history view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    control_plane_store_mode: str = Field(
        description="Configured provider-operations store mode backing control-plane truth."
    )
    reset_actions_supported: bool = Field(
        description="Whether governed provider-operations reset actions are currently supported."
    )
    supported_action_types: list[ProviderOperationsControlActionType] = Field(
        description="Supported provider-operations control action types."
    )
    latest_events: list[ProviderOperationsControlEventDescriptor] = Field(
        default_factory=list,
        description="Most recent recorded provider-operations control-plane actions.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes describing reset and rollover semantics for the provider control plane.",
    )
