from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditReadScopeMode(str, Enum):
    RESTRICTED_TENANTS = "RESTRICTED_TENANTS"
    ALL_TENANTS = "ALL_TENANTS"


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


class AuditAccessOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    NOT_FOUND = "NOT_FOUND"


class AuditAccessEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    caller_app: str = Field(min_length=1, max_length=128)
    caller_trust_source: str = Field(min_length=1, max_length=64)
    scope_mode: AuditReadScopeMode
    operation: AuditAccessOperation
    outcome: AuditAccessOutcome
    returned_record_count: int = Field(ge=0, le=100)
    recorded_at: str = Field(min_length=1, max_length=64)


INTERNAL_AGGREGATE_AUDIT_SCOPE = AuditReadScope.all_tenants()
