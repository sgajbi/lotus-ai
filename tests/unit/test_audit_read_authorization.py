from fastapi import HTTPException
import pytest

from app.config import settings
from app.contracts.audit_access import AuditReadScopeMode
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.audit_read_authorization import resolve_audit_read_scope


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
        AuthenticatedCaller(caller_app=caller_app, trust_source="trusted_http_header")
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
        AuthenticatedCaller(caller_app="lotus-manage", trust_source="trusted_http_header")
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
            AuthenticatedCaller(caller_app="lotus-platform", trust_source="trusted_http_header")
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
        AuthenticatedCaller(caller_app="lotus-platform", trust_source="trusted_http_header")
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
            AuthenticatedCaller(caller_app="lotus-platform", trust_source="trusted_http_header")
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
        AuthenticatedCaller(caller_app="lotus-platform", trust_source=trust_source)
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
            AuthenticatedCaller(caller_app="lotus-platform", trust_source="unverified_internal")
        )

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("caller_app", ["lotus-gateway", "lotus-workbench", "unknown-app"])
def test_resolve_audit_read_scope_denies_empty_or_unknown_policy(caller_app: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_audit_read_scope(
            AuthenticatedCaller(caller_app=caller_app, trust_source="trusted_http_header")
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Caller is not authorized to inspect lotus-ai audit records."
