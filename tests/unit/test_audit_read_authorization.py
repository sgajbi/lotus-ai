from fastapi import HTTPException
import pytest

from app.config import settings
from app.contracts.audit_access import AuditReadScopeMode
from app.http.authenticated_caller import AuthenticatedCaller
from app.contracts.audit_access import AuditAccessOperation
from app.services.audit_read_authorization import resolve_audit_read_scope
from pathlib import Path
from app.contracts.access_control import (
    CallerLifecycleStatus,
    CallerPolicyDescriptor,
    TenantPolicyMode,
)
from app.contracts.audit_access import AuditAccessDenialReason, AuditAccessOutcome
from app.services.audit_store import get_audit_store, reset_audit_store_cache
from tests.support.migration_runner import upgrade_database_to_head


@pytest.mark.parametrize(
    ("caller_app", "expected_tenants"),
    [
        ("lotus-manage", frozenset({"tenant-sg-001"})),
        ("lotus-advise", frozenset({"tenant-sg-001", "tenant-us-002"})),
    ],
)
def test_resolve_audit_read_scope_uses_policy_tenants(
    caller_app: str,
    expected_tenants: frozenset[str],
) -> None:
    scope = resolve_audit_read_scope(
        AuthenticatedCaller(caller_app=caller_app, trust_source="trusted_http_header"),
        operation=AuditAccessOperation.LIST_RECORDS,
    )

    assert scope.mode == AuditReadScopeMode.RESTRICTED_TENANTS
    assert scope.tenant_ids == expected_tenants
    assert scope.include_legacy_unattributed is False


def test_resolve_audit_read_scope_keeps_restricted_tenant_access_in_promoted_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "startup_readiness_policy", "enforce")
    monkeypatch.setattr(settings, "readiness_probe_policy", "degrade")

    scope = resolve_audit_read_scope(
        AuthenticatedCaller(caller_app="lotus-manage", trust_source="trusted_http_header"),
        operation=AuditAccessOperation.LIST_RECORDS,
    )

    assert scope.mode == AuditReadScopeMode.RESTRICTED_TENANTS
    assert scope.tenant_ids == frozenset({"tenant-sg-001"})
    assert scope.include_legacy_unattributed is False


def test_resolve_audit_read_scope_denies_header_operator_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", False)

    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-platform", trust_source="trusted_http_header"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Caller is not authorized to inspect lotus-ai audit records."


@pytest.mark.parametrize(
    ("startup_policy", "readiness_policy"),
    [
        ("warn", "observe"),
        ("warn", "degrade"),
        ("enforce", "observe"),
        ("enforce", "degrade"),
    ],
)
def test_resolve_audit_read_scope_allows_header_operator_only_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
    startup_policy: str,
    readiness_policy: str,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    monkeypatch.setattr(settings, "startup_readiness_policy", startup_policy)
    monkeypatch.setattr(settings, "readiness_probe_policy", readiness_policy)

    scope = resolve_audit_read_scope(
        AuthenticatedCaller(caller_app="lotus-platform", trust_source="trusted_http_header"),
        operation=AuditAccessOperation.LIST_RECORDS,
    )

    assert scope.mode == AuditReadScopeMode.ALL_TENANTS
    assert scope.tenant_ids == frozenset()
    assert scope.include_legacy_unattributed is True


@pytest.mark.parametrize(
    ("startup_policy", "readiness_policy"),
    [
        ("warn", "observe"),
        ("warn", "degrade"),
        ("enforce", "degrade"),
        ("enforce", "observe"),
        ("unknown", "observe"),
    ],
)
def test_resolve_audit_read_scope_denies_header_operator_when_disabled_independent_of_readiness(
    monkeypatch: pytest.MonkeyPatch,
    startup_policy: str,
    readiness_policy: str,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", False)
    monkeypatch.setattr(settings, "startup_readiness_policy", startup_policy)
    monkeypatch.setattr(settings, "readiness_probe_policy", readiness_policy)

    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-platform", trust_source="trusted_http_header"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Caller is not authorized to inspect lotus-ai audit records."


@pytest.mark.parametrize("trust_source", ["verified_service_jwt", "mtls_san"])
def test_resolve_audit_read_scope_allows_verified_operator_in_promoted_posture(
    monkeypatch: pytest.MonkeyPatch,
    trust_source: str,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", False)
    monkeypatch.setattr(settings, "startup_readiness_policy", "enforce")
    monkeypatch.setattr(settings, "readiness_probe_policy", "degrade")

    scope = resolve_audit_read_scope(
        AuthenticatedCaller(caller_app="lotus-platform", trust_source=trust_source),
        operation=AuditAccessOperation.LIST_RECORDS,
    )

    assert scope.mode == AuditReadScopeMode.ALL_TENANTS


def test_resolve_audit_read_scope_denies_unknown_operator_trust_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    monkeypatch.setattr(settings, "startup_readiness_policy", "warn")
    monkeypatch.setattr(settings, "readiness_probe_policy", "observe")

    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-platform", trust_source="unverified_internal"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("caller_app", ["lotus-gateway", "lotus-workbench", "unknown-app"])
def test_resolve_audit_read_scope_denies_empty_or_unknown_policy(caller_app: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app=caller_app, trust_source="trusted_http_header"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Caller is not authorized to inspect lotus-ai audit records."


def test_resolve_audit_read_scope_fails_closed_on_degenerate_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.contracts.access_control import (
        CallerLifecycleStatus,
        CallerPolicyDescriptor,
        TenantPolicyMode,
    )

    def _policy(restricted: list[str]) -> CallerPolicyDescriptor:
        return CallerPolicyDescriptor(
            caller_app="lotus-degenerate",
            lifecycle_status=CallerLifecycleStatus.ACTIVE,
            description="degenerate policy for fail-closed proof",
            allowed_task_ids=[],
            allowed_retrieval_source_ids=[],
            allow_live_provider=False,
            allow_async_control=False,
            allow_prompt_control=False,
            allow_provider_control=False,
            allow_audit_read_all_tenants=False,
            tenant_policy_mode=TenantPolicyMode.RESTRICTED,
            restricted_tenant_ids=restricted,
        )

    class _StubPolicies:
        def __init__(self, policy: object) -> None:
            self._policy = policy

        def get_policy(self, caller_app: str) -> object:
            return self._policy

    caller = AuthenticatedCaller(caller_app="lotus-degenerate", trust_source="trusted_http_header")

    # A restricted policy with NO tenants grants nothing - never everything.
    monkeypatch.setattr(
        "app.services.audit_read_authorization.get_caller_policy_repository",
        lambda: _StubPolicies(_policy([])),
    )
    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(caller, operation=AuditAccessOperation.LIST_RECORDS)
    assert exc_info.value.status_code == 403

    # A malformed tenant id (surrounding whitespace) fails closed too.
    monkeypatch.setattr(
        "app.services.audit_read_authorization.get_caller_policy_repository",
        lambda: _StubPolicies(_policy([" tenant-sg-001 "])),
    )
    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(caller, operation=AuditAccessOperation.LIST_RECORDS)
    assert exc_info.value.status_code == 403


# --- Refusals leave a record (issue #167, S1) -----------------------------


def _denial_policy(
    *,
    lifecycle: CallerLifecycleStatus = CallerLifecycleStatus.ACTIVE,
    all_tenants: bool = False,
    restricted: list[str] | None = None,
) -> CallerPolicyDescriptor:
    return CallerPolicyDescriptor(
        caller_app="lotus-denied",
        lifecycle_status=lifecycle,
        description="policy under test",
        allowed_task_ids=[],
        allowed_retrieval_source_ids=[],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=all_tenants,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        restricted_tenant_ids=restricted if restricted is not None else [],
    )


class _Policies:
    def __init__(self, policy: object) -> None:
        self._policy = policy

    def get_policy(self, caller_app: str) -> object:
        return self._policy


def _install_policy(monkeypatch: pytest.MonkeyPatch, policy: object) -> None:
    monkeypatch.setattr(
        "app.services.audit_read_authorization.get_caller_policy_repository",
        lambda: _Policies(policy),
    )


@pytest.mark.parametrize(
    ("policy", "trust_source", "expected_reason"),
    [
        (None, "trusted_http_header", AuditAccessDenialReason.NO_POLICY),
        (
            _denial_policy(lifecycle=CallerLifecycleStatus.DISABLED),
            "trusted_http_header",
            AuditAccessDenialReason.INACTIVE_POLICY,
        ),
        (
            _denial_policy(all_tenants=True, restricted=["tenant-sg-001"]),
            "verified_service_jwt",
            AuditAccessDenialReason.CONFLICTING_POLICY,
        ),
        (
            _denial_policy(all_tenants=True),
            "trusted_http_header",
            AuditAccessDenialReason.UNVERIFIED_TRUST_SOURCE,
        ),
        (_denial_policy(), "trusted_http_header", AuditAccessDenialReason.NO_TENANT_SCOPE),
        (
            _denial_policy(restricted=[" tenant-sg-001 "]),
            "trusted_http_header",
            AuditAccessDenialReason.MALFORMED_POLICY,
        ),
    ],
)
def test_every_refusal_path_records_exactly_one_denied_event(
    policy: object,
    trust_source: str,
    expected_reason: AuditAccessDenialReason,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The attempts a security reviewer most needs used to leave no trace: every
    403 was raised before any evidence was written."""

    settings.local_header_caller_identity_enabled = False
    _install_policy(monkeypatch, policy)
    caller = AuthenticatedCaller(caller_app="lotus-denied", trust_source=trust_source)

    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(caller, operation=AuditAccessOperation.GET_RECORD)
    assert exc_info.value.status_code == 403

    events = list(get_audit_store().list_access_events(limit=10))
    assert len(events) == 1
    event = events[0]
    assert event.outcome is AuditAccessOutcome.DENIED
    assert event.denial_reason is expected_reason
    assert event.operation is AuditAccessOperation.GET_RECORD
    assert event.caller_app == "lotus-denied"
    assert event.caller_trust_source == trust_source
    # The scope was never resolved, so the event says so rather than naming a
    # scope the caller did not reach.
    assert event.scope_mode is AuditReadScopeMode.UNRESOLVED
    assert event.returned_record_count == 0


def test_a_misconfigured_grant_and_an_unverified_caller_are_not_the_same_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """These two used to share one branch.

    One is a policy that grants all-tenant access while also carrying tenant
    restrictions - a configuration mistake. The other is a caller presenting an
    unverified identity for a privileged read - #161's fence, and the entry
    most worth investigating. Recording both as one reason would hide the
    security event inside the misconfiguration.
    """

    settings.local_header_caller_identity_enabled = False

    _install_policy(monkeypatch, _denial_policy(all_tenants=True, restricted=["tenant-sg-001"]))
    with pytest.raises(HTTPException):
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-denied", trust_source="verified_service_jwt"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )

    _install_policy(monkeypatch, _denial_policy(all_tenants=True))
    with pytest.raises(HTTPException):
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-denied", trust_source="trusted_http_header"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )

    reasons = [event.denial_reason for event in get_audit_store().list_access_events(limit=10)]
    assert set(reasons) == {
        AuditAccessDenialReason.CONFLICTING_POLICY,
        AuditAccessDenialReason.UNVERIFIED_TRUST_SOURCE,
    }


def test_a_refusal_whose_evidence_cannot_be_written_is_not_a_clean_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The denial-path twin of the existing success-path proof.

    A refusal that could not be recorded must not return a tidy 403 as though
    nothing happened - the entire point of the slice is that refusals leave a
    trace, so a failure to leave one is a server error.
    """

    settings.local_header_caller_identity_enabled = False
    _install_policy(monkeypatch, None)

    class _FailingStore:
        def save_access_event(self, event: object) -> None:
            raise RuntimeError("access-event store unavailable")

    monkeypatch.setattr(
        "app.services.audit_read_authorization.get_audit_store", lambda: _FailingStore()
    )

    with pytest.raises(RuntimeError):
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-denied", trust_source="trusted_http_header"),
            operation=AuditAccessOperation.LIST_RECORDS,
        )


def test_denial_reasons_survive_the_sql_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence that only survives in memory is not evidence a reviewer can
    come back to."""

    settings.audit_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-denials.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_audit_store_cache()
    settings.local_header_caller_identity_enabled = False
    _install_policy(monkeypatch, _denial_policy(all_tenants=True))

    with pytest.raises(HTTPException):
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app="lotus-denied", trust_source="trusted_http_header"),
            operation=AuditAccessOperation.AGGREGATE_BREAKDOWNS,
        )

    reset_audit_store_cache()
    events = list(get_audit_store().list_access_events(limit=10))
    assert len(events) == 1
    assert events[0].outcome is AuditAccessOutcome.DENIED
    assert events[0].denial_reason is AuditAccessDenialReason.UNVERIFIED_TRUST_SOURCE
    assert events[0].operation is AuditAccessOperation.AGGREGATE_BREAKDOWNS
