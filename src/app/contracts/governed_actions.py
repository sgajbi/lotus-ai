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
    # Clearing an operator capability degradation re-exposes an
    # evidence-derived capability fact to requirement routing - risk-increasing,
    # so it takes the same two-step flow (issue #245, slice 2).
    MODEL_CAPABILITY_RESTORE = "MODEL_CAPABILITY_RESTORE"
    # Tenant erasure permanently destroys client-derived rows across every
    # tenant-erasable family (issue #158, S3): governed two-step, receipt
    # signed - legal hold overrides it, and both are recorded.
    DATA_ERASURE = "DATA_ERASURE"
    # Adding an identity to the serving policy widens what may serve
    # (issue #295, S2) - risk-increasing, so it takes the two-step flow.
    # Removal is risk-reducing and follows the safety direction: one
    # verified principal, immediate, approved_by honestly null.
    SERVING_POLICY_IDENTITY_ADD = "SERVING_POLICY_IDENTITY_ADD"
    # Runtime-originated: a worker quarantining or redriving a poisoned queue
    # job answers to a service identity, not a human approver, and is
    # explicitly SYSTEM_ORIGINATED rather than dressing a service string up
    # as an approval (issue #157).
    ASYNC_QUEUE_RECOVERY = "ASYNC_QUEUE_RECOVERY"
    # Settling an unresolved billable exposure to an operator-evidenced
    # charge releases hard-budget admission headroom (issue #329) -
    # risk-increasing, so it takes the two-step flow. Holding exposure is the
    # automatic safe direction and needs no approval.
    BUDGET_RECONCILIATION = "BUDGET_RECONCILIATION"
    # Releasing a frozen claim re-opens a dangerous action to approval
    # (issue #340) - risk-increasing, two-step, and additionally requiring
    # BOTH credentials to differ from the frozen claim's credential. The
    # automatic path (TTL/lease) is explicitly rejected: it would re-open
    # the one-owner window #327 closed.
    CLAIM_RELEASE = "CLAIM_RELEASE"


class GovernedActionStatus(str, Enum):
    PENDING = "PENDING"
    # An approver's atomic claim on a PENDING action (issue #327): exactly one
    # approval session owns the transition to execution; a claim that survives
    # a crash is resumable only by the claiming credential.
    CLAIMED = "CLAIMED"
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
    claimed_at: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Instant the approver's atomic claim transitioned this action from "
            "PENDING (issue #327); execution evidence begins here."
        ),
    )
    result_payload: dict[str, object] | None = Field(
        default=None,
        description=(
            "Durable domain result of the executed action (issue #327), persisted "
            "with the EXECUTED transition so evidence-bearing responses (e.g. an "
            "erasure receipt) are retrievable after a lost response without "
            "re-executing the effect."
        ),
    )
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


class ClaimReleaseIntentRequest(BaseModel):
    """Step one of governed claim release (issue #340).

    Re-opens a frozen CLAIMED action to approval - risk-increasing, so a
    verified requester states the intent and a DISTINCT verified credential
    approves the exact hash; BOTH must also differ from the frozen claim's
    credential, so the release is never a self-service second path to
    execution.
    """

    target_action_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(
        min_length=1,
        description="Why the claim is considered frozen (credential rotated, operator gone).",
    )
    requested_by: str | None = Field(default=None, max_length=256)


class ClaimReleaseApprovalRequest(BaseModel):
    """Step two: a distinct verified credential approves the exact pending action."""

    action_id: str = Field(min_length=1, max_length=64)
    action_hash: str = Field(min_length=64, max_length=64)
    approved_by: str | None = Field(default=None, max_length=256)
    resume_interrupted_claim: bool = Field(
        default=False,
        description=(
            "Explicit recovery intent (issue #327): resume a claim this same "
            "credential holds after a crash. Never inferred; refused for any "
            "other credential's claim."
        ),
    )


class ClaimReleaseApprovalResponse(BaseModel):
    service: str = Field(description="Publishing service identity.")
    version: str = Field(description="Publishing service version.")
    governed_action: GovernedActionRecord = Field(
        description="The executed CLAIM_RELEASE action carrying the full evidence chain."
    )
    released_action: GovernedActionRecord = Field(
        description="The target action after release: PENDING again, requester evidence intact."
    )
    summary: list[str] = Field(description="Human-readable statements about the release.")


class GovernedActionHistoryResponse(BaseModel):
    """Governed-action evidence records, newest requested first.

    The read the approval flow's own refusal guidance presupposes: an approver
    reviews the exact pending action (payload and hash) before approving it,
    and an auditor reads the request-approval-execution chain - including
    evidence that lives nowhere else, such as a capability degradation cleared
    by an executed restore.
    """

    service: str = Field(description="Publishing service identity.")
    version: str = Field(description="Publishing service version.")
    actions: list[GovernedActionRecord] = Field(
        description="Matching governed-action records, newest requested first.",
    )
