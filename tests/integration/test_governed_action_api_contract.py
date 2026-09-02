"""API contract for the governed-action evidence read (issue #157).

The approval flow's own guidance - "review the pending action and approve its
hash" - presupposes this read: a distinct approver inspects the exact pending
payload and hash before approving, and an auditor reads the evidence chain.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.governed_action_control import record_system_originated_action
from app.contracts.governed_actions import GovernedActionType


def test_governed_action_history_route(client: TestClient) -> None:
    record_system_originated_action(
        service_identity="worker-alpha-01",
        action_type=GovernedActionType.ASYNC_QUEUE_RECOVERY,
        target="asyncjob_http_contract",
        payload={"action": "QUARANTINE_QUEUED_JOB", "reason": "poisoned payload"},
    )

    response = client.get("/platform/governed-actions")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    actions = {action["target"]: action for action in body["actions"]}
    listed = actions["asyncjob_http_contract"]
    assert listed["actor_class"] == "SYSTEM_ORIGINATED"
    assert listed["status"] == "EXECUTED"
    assert listed["action_hash"]
    assert listed["action_payload"]["action"] == "QUARANTINE_QUEUED_JOB"

    filtered = client.get(
        "/platform/governed-actions",
        params={"status": "PENDING", "target": "asyncjob_http_contract"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["actions"] == []

    bounded = client.get("/platform/governed-actions", params={"limit": 500})
    assert bounded.status_code == 422
