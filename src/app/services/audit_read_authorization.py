from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from typing import NoReturn

from fastapi import HTTPException, status

from app.contracts.access_control import CallerLifecycleStatus
from app.contracts.audit_access import (
    AuditAccessDenialReason,
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


def resolve_audit_read_scope(
    caller: AuthenticatedCaller, *, operation: AuditAccessOperation
) -> AuditReadScope:
    """Resolve the caller's audit read scope, recording every refusal.

    A refused privileged read is the entry a security reviewer most wants and
    the one that used to leave no trace anywhere: every 403 below was raised
    before any evidence was written (issue #167). The event is written before
    the refusal is raised, so a store failure surfaces as a 5xx rather than
    turning a refusal into a clean, unrecorded 403.

    ``operation`` is what the caller was attempting. The scope is deliberately
    not a parameter: at refusal time it has not been resolved, which is what
    ``AuditReadScopeMode.UNRESOLVED`` records.
    """

    policy = get_caller_policy_repository().get_policy(caller.caller_app)
    if policy is None:
        _refuse(caller, operation, AuditAccessDenialReason.NO_POLICY)
    if policy.lifecycle_status != CallerLifecycleStatus.ACTIVE:
        _refuse(caller, operation, AuditAccessDenialReason.INACTIVE_POLICY)

    tenant_ids = _normalized_tenant_ids(policy.restricted_tenant_ids, caller, operation)
    if policy.allow_audit_read_all_tenants:
        # Two distinct failures, deliberately not one branch. A grant that also
        # carries tenant restrictions is a misconfiguration; an unverified
        # caller reaching for privileged access is a security event. Collapsing
        # them would hide the second inside the first.
        if tenant_ids:
            _refuse(caller, operation, AuditAccessDenialReason.CONFLICTING_POLICY)
        if not is_privileged_caller_identity_accepted(caller):
            _refuse(caller, operation, AuditAccessDenialReason.UNVERIFIED_TRUST_SOURCE)
        return AuditReadScope.all_tenants()
    if not tenant_ids:
        _refuse(caller, operation, AuditAccessDenialReason.NO_TENANT_SCOPE)
    return AuditReadScope.restricted(tenant_ids)


def _refuse(
    caller: AuthenticatedCaller,
    operation: AuditAccessOperation,
    reason: AuditAccessDenialReason,
) -> NoReturn:
    """Record the refusal, then raise it."""

    get_audit_store().save_access_event(
        AuditAccessEvent(
            event_id=str(uuid4()),
            caller_app=caller.caller_app,
            caller_trust_source=caller.trust_source,
            scope_mode=AuditReadScopeMode.UNRESOLVED,
            operation=operation,
            outcome=AuditAccessOutcome.DENIED,
            denial_reason=reason,
            returned_record_count=0,
            recorded_at=datetime.now(UTC).isoformat(),
        )
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_DENIED_DETAIL)


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


def _normalized_tenant_ids(
    values: list[str], caller: AuthenticatedCaller, operation: AuditAccessOperation
) -> frozenset[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            _refuse(caller, operation, AuditAccessDenialReason.MALFORMED_POLICY)
        normalized.add(value)
    return frozenset(normalized)
