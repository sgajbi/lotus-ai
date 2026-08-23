from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.access_control import CallerLifecycleStatus
from app.contracts.audit_access import (
    AuditAccessEvent,
    AuditAccessOperation,
    AuditAccessOutcome,
    AuditReadScope,
    AuditReadScopeMode,
)
from app.http.authenticated_caller import (
    AuthenticatedCaller,
    is_privileged_caller_identity_accepted,
)
from app.services.audit_store import get_audit_store
from app.services.caller_policy_store import get_caller_policy_repository

_ACCESS_DENIED_DETAIL = "Caller is not authorized to inspect lotus-ai audit records."


def resolve_audit_read_scope(caller: AuthenticatedCaller) -> AuditReadScope:
    policy = get_caller_policy_repository().get_policy(caller.caller_app)
    if policy is None or policy.lifecycle_status != CallerLifecycleStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_DENIED_DETAIL)

    tenant_ids = _normalized_tenant_ids(policy.restricted_tenant_ids)
    if policy.allow_audit_read_all_tenants:
        if tenant_ids or not is_privileged_caller_identity_accepted(caller):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_DENIED_DETAIL)
        return AuditReadScope.all_tenants()
    if not tenant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_DENIED_DETAIL)
    return AuditReadScope.restricted(tenant_ids)


def record_all_tenant_audit_access(
    *,
    caller: AuthenticatedCaller,
    scope: AuditReadScope,
    operation: AuditAccessOperation,
    outcome: AuditAccessOutcome,
    returned_record_count: int,
) -> None:
    if scope.mode != AuditReadScopeMode.ALL_TENANTS:
        return
    get_audit_store().save_access_event(
        AuditAccessEvent(
            event_id=f"audit_access_{uuid4().hex}",
            caller_app=caller.caller_app,
            caller_trust_source=caller.trust_source,
            scope_mode=scope.mode,
            operation=operation,
            outcome=outcome,
            returned_record_count=returned_record_count,
            recorded_at=datetime.now(UTC).isoformat(),
        )
    )


def _normalized_tenant_ids(values: list[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_DENIED_DETAIL)
        normalized.add(value)
    return frozenset(normalized)
