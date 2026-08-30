"""Scoped AI kill switches (issue #177, slice 1).

A kill switch is an explicit operator decision to stop live AI execution for a
scope - distinct from the circuit breaker (automatic health protection) and
from workflow-pack PAUSE (pack-granularity registration control). Activations
are durable, attributable, optionally time-bounded, and enforced at the
provider gateway preflight, where a hit becomes a recorded routing rejection
(issue #176) with the bounded KILL_SWITCH_ACTIVE category.

Two semantics exist (issue #177 S3). HARD_KILL refuses everything in scope
immediately - new synchronous executions, new async intake, and the execution
of already-queued work. DRAIN stops intake (new synchronous executions and new
async submissions are refused) while already-claimed async workflow-pack jobs
are allowed to complete safely; synchronous requests are never drained - they
refuse immediately under either semantics.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class KillSwitchSemantics(str, Enum):
    HARD_KILL = "HARD_KILL"
    DRAIN = "DRAIN"


class KillSwitchScope(str, Enum):
    ALL_LIVE_TEXT = "ALL_LIVE_TEXT"
    PROVIDER = "PROVIDER"
    MODEL_REVISION = "MODEL_REVISION"
    TASK = "TASK"
    TENANT = "TENANT"
    CALLER_APP = "CALLER_APP"


TARGETLESS_KILL_SWITCH_SCOPES = frozenset({KillSwitchScope.ALL_LIVE_TEXT})


class KillSwitchActivationRecord(BaseModel):
    """One durable kill-switch activation, including its clearance when cleared."""

    switch_id: str = Field(min_length=1, description="Server-assigned activation identity.")
    scope: KillSwitchScope = Field(description="What kind of target this switch disables.")
    semantics: KillSwitchSemantics = Field(
        default=KillSwitchSemantics.HARD_KILL,
        description="HARD_KILL refuses all in-scope execution immediately; DRAIN refuses "
        "new intake while already-claimed async work completes safely.",
    )
    target: str | None = Field(
        default=None,
        description="Scope target (provider id, model revision, task id, tenant id, or "
        "caller app); null only for targetless scopes.",
    )
    reason: str = Field(min_length=1, description="Operator reason recorded at activation.")
    requested_by: str = Field(min_length=1, description="Operator who requested activation.")
    approved_by: str = Field(min_length=1, description="Operator who approved activation.")
    activated_at: str = Field(description="Instant the switch became active (UTC).")
    expires_at_utc: str | None = Field(
        default=None,
        description="Optional expiry instant (UTC); an expired switch is inert but retained.",
    )
    cleared_at: str | None = Field(
        default=None,
        description="Instant the switch was cleared; null while active.",
    )
    cleared_by: str | None = Field(
        default=None,
        description="Operator who cleared the switch; null while active.",
    )
    clear_reason: str | None = Field(
        default=None,
        description="Operator reason recorded at clearance; null while active.",
    )


class KillSwitchActivationRequest(BaseModel):
    caller_app: str = Field(min_length=1, description="Calling application identity.")
    scope: KillSwitchScope = Field(description="What kind of target to disable.")
    semantics: KillSwitchSemantics = Field(
        default=KillSwitchSemantics.HARD_KILL,
        description="HARD_KILL (default) refuses all in-scope execution immediately; "
        "DRAIN refuses new intake while already-claimed async work completes.",
    )
    target: str | None = Field(
        default=None,
        description="Scope target; required for every scope except targetless ones.",
    )
    reason: str = Field(min_length=1, description="Why this switch is being activated.")
    requested_by: str = Field(min_length=1, description="Operator requesting activation.")
    approved_by: str = Field(min_length=1, description="Operator approving activation.")
    expires_at_utc: str | None = Field(
        default=None,
        description="Optional expiry instant (UTC ISO-8601).",
    )


class KillSwitchClearRequest(BaseModel):
    caller_app: str = Field(min_length=1, description="Calling application identity.")
    reason: str = Field(min_length=1, description="Why this switch is being cleared.")
    requested_by: str = Field(min_length=1, description="Operator requesting clearance.")
    approved_by: str = Field(min_length=1, description="Operator approving clearance.")


class KillSwitchActionResponse(BaseModel):
    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where kill-switch truth lives: memory or sqlalchemy.")
    activation: KillSwitchActivationRecord = Field(
        description="The activation this action created or cleared.",
    )
    summary: list[str] = Field(description="Human-readable statements about the action.")


class KillSwitchStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where kill-switch truth lives: memory or sqlalchemy.")
    active_count: int = Field(ge=0, description="Number of currently enforcing activations.")
    activations: list[KillSwitchActivationRecord] = Field(
        description="Every recorded activation, newest first, including cleared and expired ones.",
    )
