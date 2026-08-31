"""Registered-caller gate on every protected route (issue #149, S2).

Identity is not authorization: an identified but unregistered caller is
refused on every protected route - including the diagnostic read surfaces
that previously answered to any identity string - while registered ACTIVE
callers read them under the PLATFORM_READ capability. Route- and
service-level capability rules still apply on top.
"""

import pytest
from fastapi.testclient import TestClient

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationOutcome,
    CallerLifecycleStatus,
)
from app.http.authenticated_caller import bind_internal_authenticated_caller
from app.main import app
from app.services.access_control_authorization import authorize_request
from app.services.caller_policy_store import get_caller_policy_repository


def _platform_read_decision(caller_app: str) -> AuthorizationOutcome:
    with bind_internal_authenticated_caller(
        caller_app=caller_app, trust_source="trusted_http_header"
    ):
        return authorize_request(
            caller_app=caller_app,
            capability_type=AuthorizationCapabilityType.PLATFORM_READ,
        ).outcome


def test_platform_read_is_granted_by_the_policy_row_itself() -> None:
    assert _platform_read_decision("lotus-manage") is AuthorizationOutcome.ALLOWED
    assert _platform_read_decision("lotus-ai-provider-operations") is AuthorizationOutcome.ALLOWED


def test_platform_read_blocks_unknown_and_disabled_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _platform_read_decision("intruder-app") is AuthorizationOutcome.BLOCKED_UNKNOWN_CALLER

    inner = get_caller_policy_repository()

    class _SuspendingRepository:
        def get_policy(self, caller_app: str) -> object:
            policy = inner.get_policy(caller_app)
            if policy is not None and caller_app == "lotus-workbench":
                return policy.model_copy(
                    update={"lifecycle_status": CallerLifecycleStatus.DISABLED}
                )
            return policy

        def list_policies(self) -> object:
            return inner.list_policies()

    monkeypatch.setattr(
        "app.services.access_control_authorization.get_caller_policy_repository",
        lambda: _SuspendingRepository(),
    )
    assert (
        _platform_read_decision("lotus-workbench") is AuthorizationOutcome.BLOCKED_CALLER_DISABLED
    )


def test_diagnostic_reads_refuse_an_unregistered_caller() -> None:
    # These surfaces previously answered to ANY identity string; the gate
    # closes exactly that gap, across several routers.
    sample_reads = [
        "/platform/runtime-status",
        "/platform/observability/runtime-status",
        "/platform/providers/routing-posture",
        "/platform/access-control/runtime-status",
    ]
    with TestClient(app) as client:
        for path in sample_reads:
            refused = client.get(path, headers={"X-Caller-App": "intruder-app"})
            assert refused.status_code == 403, f"{path} answered an unregistered caller"
            assert refused.json()["error_code"] == "LOTUS_AI_CALLER_FORBIDDEN"

        for path in sample_reads:
            allowed = client.get(path, headers={"X-Caller-App": "lotus-platform"})
            assert allowed.status_code == 200, f"{path} refused a registered caller"


def test_the_recorder_identity_reaches_its_protected_route() -> None:
    # The internal recorder identity is a registered caller like any other;
    # its route's own service rule still applies on top of the gate.
    with TestClient(app) as client:
        response = client.post(
            "/platform/provider-operations/workflow-runs/run_missing/retention-confirmations",
            json={
                "recorded_by": "lotus-ai-provider-operations",
                "provider_id": "text.local",
                "retention_mode": "ZERO_RETENTION_REQUESTED",
                "deletion_state": "CONFIRMED_DELETED",
                "evidence_ref": "provider-ops:retention:run_missing",
            },
            headers={"X-Caller-App": "lotus-ai-provider-operations"},
        )
        # Past the registered-caller gate: the route's own validation answers
        # (unknown run / contract detail), not the gate's 403.
        assert response.status_code != 403
