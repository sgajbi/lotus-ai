from __future__ import annotations

from fastapi.testclient import TestClient
from _pytest.monkeypatch import MonkeyPatch

from app.contracts.access_control import (
    CallerLifecycleStatus,
    CallerPolicyDescriptor,
    TenantPolicyMode,
)


def test_protected_task_route_requires_authenticated_caller(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        headers={"X-Caller-App": ""},
        json=_task_request("lotus-manage"),
    )

    assert response.status_code == 403
    assert "Authenticated caller identity is required" in response.json()["detail"]


def test_protected_task_route_blocks_spoofed_body_caller(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        headers={"X-Caller-App": "lotus-platform"},
        json=_task_request("lotus-manage"),
    )

    assert response.status_code == 403
    assert "does not match the authenticated HTTP caller identity" in response.json()["detail"]


def test_protected_task_route_records_authenticated_caller_binding(
    client: TestClient,
) -> None:
    response = client.post(
        "/ai/tasks/execute",
        headers={"X-Caller-App": "lotus-manage"},
        json=_task_request("lotus-manage"),
    )

    assert response.status_code == 200
    authorization = response.json()["audit"]["authorization"]
    assert authorization["caller_app"] == "lotus-manage"
    assert authorization["authenticated_caller_app"] == "lotus-manage"
    assert authorization["caller_identity_source"] == "trusted_http_header"
    assert authorization["caller_identity_bound"] is True
    assert authorization["outcome"] == "ALLOWED"


def test_protected_task_route_blocks_unknown_authenticated_caller(
    client: TestClient,
) -> None:
    response = client.post(
        "/ai/tasks/execute",
        headers={"X-Caller-App": "unknown-app"},
        json=_task_request("unknown-app", tenant_id=None),
    )

    assert response.status_code == 403
    assert "not registered" in response.json()["detail"]


def test_protected_task_route_blocks_disabled_authenticated_caller(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    disabled_policy = CallerPolicyDescriptor(
        caller_app="disabled-app",
        lifecycle_status=CallerLifecycleStatus.DISABLED,
        description="Disabled caller seeded for authenticated-caller boundary testing.",
        allowed_task_ids=["explain.v1"],
        allowed_retrieval_source_ids=[],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        restricted_tenant_ids=[],
    )

    class FakeCallerPolicyRepository:
        def list_policies(self) -> list[CallerPolicyDescriptor]:
            return [disabled_policy]

        def get_policy(self, caller_app: str) -> CallerPolicyDescriptor | None:
            if caller_app == disabled_policy.caller_app:
                return disabled_policy
            return None

    monkeypatch.setattr(
        "app.services.access_control_authorization.get_caller_policy_repository",
        lambda: FakeCallerPolicyRepository(),
    )

    response = client.post(
        "/ai/tasks/execute",
        headers={"X-Caller-App": "disabled-app"},
        json=_task_request("disabled-app", tenant_id=None),
    )

    assert response.status_code == 403
    assert "currently disabled" in response.json()["detail"]


def test_protected_prompt_control_route_requires_authenticated_caller(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/prompts/control-actions",
        headers={"X-Caller-App": ""},
        json=_prompt_control_request("lotus-platform"),
    )

    assert response.status_code == 403
    assert "Authenticated caller identity is required" in response.json()["detail"]


def test_prompt_control_ignores_any_body_caller_and_follows_the_authenticated_identity(
    client: TestClient,
) -> None:
    """The stronger form of the old spoofed-body-caller check: the contract no
    longer carries a caller identity at all (issue #157), so a claimed
    caller_app in the body is inert and authorization follows only the
    authenticated caller - which here lacks prompt control and is refused."""

    response = client.post(
        "/platform/prompts/control-actions",
        headers={"X-Caller-App": "lotus-workbench"},
        json=_prompt_control_request("lotus-platform"),
    )

    assert response.status_code == 403
    assert "not authorized for prompt control-plane actions" in response.json()["detail"]


def _task_request(caller_app: str, *, tenant_id: str | None = "tenant-sg-001") -> dict[str, object]:
    caller: dict[str, str] = {
        "caller_app": caller_app,
        "correlation_id": f"corr-auth-boundary-{caller_app}",
    }
    if tenant_id is not None:
        caller["tenant_id"] = tenant_id
    return {
        "task_id": "explain.v1",
        "input_mode": "STRUCTURED_CONTEXT",
        "caller": caller,
        "context": {
            "summary": "Explain rebalance outcome",
            "payload": {"status": "BLOCKED", "violations": 2},
            "source_refs": ["lotus-manage:run:auth-boundary"],
        },
        "expected_output_label": "EXPLANATION_ONLY",
    }


def _prompt_control_request(caller_app: str) -> dict[str, object]:
    return {
        "task_id": "explain.v1",
        "action_type": "PROMOTE_CANDIDATE",
        "caller_app": caller_app,
        "candidate_prompt_version": "foundation.explain.v2",
        "requested_by": "alice@lotus.test",
        "approved_by": "bob@lotus.test",
        "reason": "Verify authenticated caller boundary.",
    }
