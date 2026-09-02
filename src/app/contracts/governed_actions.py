"""Governed control-plane actions (issue #157, slice 1).

One reusable pattern for high-impact permissive actions, proven first through
kill-switch clearance. The risk-direction rule: a safety-increasing action
(activate a switch, retire a model) takes one verified principal and executes
immediately; a risk-increasing action (clear a switch, promote a prompt or
model, enable a provider) takes a verified requester, a verified DISTINCT
approver, and a hash binding the approval to the exact action requested.

No verified human principal exists in the identity model today - the caller
credential's ``sub`` names an application - so dual control binds to the
signing credential (``credential_key_id``). Two steps signed by two different
key ids are genuinely two different credentials; a single compromised
credential cannot both request and approve. Claimed operator names are
recorded as UNVERIFIED ATTRIBUTION, never as approval evidence: the credential
is the fact, the name is a claim.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GovernedActorClass(str, Enum):
    """Who a governed action answers to.

    Explicit, never inferred from a name that happens to look like a service.
    A runtime-originated action (a worker quarantining a poisoned job) is
    legitimate and has no human approver; recording it as HUMAN_APPROVED with
    a service string in the approver field is exactly the bypass this exists
    to close.
    """

    HUMAN_APPROVED = "HUMAN_APPROVED"
    SYSTEM_ORIGINATED = "SYSTEM_ORIGINATED"


class GovernedActionType(str, Enum):
    KILL_SWITCH_CLEAR = "KILL_SWITCH_CLEAR"
    PROMPT_PROMOTE = "PROMPT_PROMOTE"
    PROVIDER_OPERATIONS_RESET = "PROVIDER_OPERATIONS_RESET"
    # Serving-posture expansion of a catalogue model (issue #245): eval
    # evidence enables the decision; a distinct verified credential makes it.
    MODEL_LIFECYCLE_PROMOTE = "MODEL_LIFECYCLE_PROMOTE"
    # Runtime-originated: a worker quarantining or redriving a poisoned queue
    # job answers to a service identity, not a human approver, and is
    # explicitly SYSTEM_ORIGINATED rather than dressing a service string up
    # as an approval (issue #157).
    ASYNC_QUEUE_RECOVERY = "ASYNC_QUEUE_RECOVERY"


class GovernedActionStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    SUPERSEDED = "SUPERSEDED"


class GovernedActionRecord(BaseModel):
    """Immutable evidence for one governed action, request through execution."""

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(min_length=1, max_length=64)
    action_type: GovernedActionType
    actor_class: GovernedActorClass
    status: GovernedActionStatus
    target: str = Field(
        min_length=1,
        max_length=256,
        description="The object this action operates on (e.g. a kill-switch id).",
    )
    action_hash: str = Field(
        min_length=64,
        max_length=64,
        description=(
            "SHA-256 over the canonical action payload. Approval binds to this hash, so "
            "approval of one action can never authorize a modified action."
        ),
    )
    action_payload: dict[str, str | None] = Field(
        description="The exact hashed payload, retained so the evidence is self-verifying.",
    )
    requester_caller_app: str = Field(min_length=1, max_length=128)
    requester_trust_source: str = Field(min_length=1, max_length=64)
    requester_key_id: str | None = Field(
        default=None,
        max_length=128,
        description="Signing credential that authenticated the requester; the verified fact.",
    )
    requester_attribution: str | None = Field(
        default=None,
        max_length=256,
        description="Caller-claimed operator name. Unverified attribution, not evidence.",
    )
    requested_at: str = Field(min_length=1, max_length=64)
    approver_caller_app: str | None = Field(default=None, max_length=128)
    approver_trust_source: str | None = Field(default=None, max_length=64)
    approver_key_id: str | None = Field(
        default=None,
        max_length=128,
        description="Signing credential that authenticated the approver; must differ from the requester's.",
    )
    approver_attribution: str | None = Field(default=None, max_length=256)
    approved_at: str | None = Field(default=None, max_length=64)
    executed_at: str | None = Field(default=None, max_length=64)
    superseded_by_action_id: str | None = Field(default=None, max_length=64)


class GovernedActionResponse(BaseModel):
    service: str = Field(description="Publishing service identity.")
    version: str = Field(description="Publishing service version.")
    governed_action: GovernedActionRecord = Field(
        description="The governed-action evidence record."
    )
    summary: list[str] = Field(description="Human-readable statements about the action.")
