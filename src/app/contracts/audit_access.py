from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditReadScopeMode(str, Enum):
    RESTRICTED_TENANTS = "RESTRICTED_TENANTS"
    ALL_TENANTS = "ALL_TENANTS"
    # A refusal happens before a scope is resolved, so a denial event has no
    # scope to report. Saying so explicitly beats reporting a scope the caller
    # never reached (issue #167).
    UNRESOLVED = "UNRESOLVED"


class AuditReadScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: AuditReadScopeMode
    tenant_ids: frozenset[str] = Field(default_factory=frozenset)
    include_legacy_unattributed: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> AuditReadScope:
        if self.mode == AuditReadScopeMode.RESTRICTED_TENANTS:
            if not self.tenant_ids:
                raise ValueError("restricted audit scope requires at least one tenant")
            if self.include_legacy_unattributed:
                raise ValueError("restricted audit scope cannot include unattributed records")
            return self
        if self.tenant_ids:
            raise ValueError("all-tenant audit scope cannot carry tenant identifiers")
        if not self.include_legacy_unattributed:
            raise ValueError("all-tenant audit scope must include legacy unattributed records")
        return self

    @classmethod
    def restricted(cls, tenant_ids: frozenset[str]) -> AuditReadScope:
        return cls(mode=AuditReadScopeMode.RESTRICTED_TENANTS, tenant_ids=tenant_ids)

    @classmethod
    def all_tenants(cls) -> AuditReadScope:
        return cls(
            mode=AuditReadScopeMode.ALL_TENANTS,
            include_legacy_unattributed=True,
        )


class AuditAccessOperation(str, Enum):
    LIST_RECORDS = "LIST_RECORDS"
    GET_RECORD = "GET_RECORD"
    AGGREGATE_BREAKDOWNS = "AGGREGATE_BREAKDOWNS"
    # Reading the access-events ledger is itself a privileged audit read, so it
    # is recorded like any other (issue #167, S2).
    LIST_ACCESS_EVENTS = "LIST_ACCESS_EVENTS"


class AuditAccessOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    NOT_FOUND = "NOT_FOUND"
    DENIED = "DENIED"


class AuditAccessDenialReason(str, Enum):
    """Why a privileged audit read was refused.

    These are kept distinct rather than collapsed into one "denied" because
    they carry different meanings for a reviewer. UNVERIFIED_TRUST_SOURCE is a
    caller presenting an unverified identity for a privileged read - the fence
    from #161, and the entry most worth investigating. CONFLICTING_POLICY is a
    misconfigured grant. Recording both as the same thing would hide the first
    inside the second.
    """

    NO_POLICY = "NO_POLICY"
    INACTIVE_POLICY = "INACTIVE_POLICY"
    CONFLICTING_POLICY = "CONFLICTING_POLICY"
    NO_TENANT_SCOPE = "NO_TENANT_SCOPE"
    MALFORMED_POLICY = "MALFORMED_POLICY"
    UNVERIFIED_TRUST_SOURCE = "UNVERIFIED_TRUST_SOURCE"
    # A caller with a valid restricted-tenant scope reaching for a surface that
    # requires the all-tenant privilege. Distinct from NO_TENANT_SCOPE, which is
    # a caller with no usable scope at all.
    INSUFFICIENT_PRIVILEGE = "INSUFFICIENT_PRIVILEGE"


class AuditAccessEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    caller_app: str = Field(min_length=1, max_length=128)
    caller_trust_source: str = Field(min_length=1, max_length=64)
    scope_mode: AuditReadScopeMode
    operation: AuditAccessOperation
    outcome: AuditAccessOutcome
    denial_reason: AuditAccessDenialReason | None = Field(
        default=None,
        description="Why access was refused; set only when the outcome is DENIED.",
    )
    returned_record_count: int = Field(ge=0, le=100)
    recorded_at: str = Field(min_length=1, max_length=64)


class AuditAccessEventCatalogResponse(BaseModel):
    """The privileged-access ledger, newest first.

    Bounded like every other audit read. The events describe who read audit
    records and who was refused; reading them requires the same all-tenant
    privilege the events themselves describe.
    """

    service: str = Field(description="Publishing service identity.")
    version: str = Field(description="Publishing service version.")
    returned_event_count: int = Field(ge=0, description="Number of events returned.")
    events: list[AuditAccessEvent] = Field(description="Access events, newest first.")


INTERNAL_AGGREGATE_AUDIT_SCOPE = AuditReadScope.all_tenants()
