"""API contract for governed tenant erasure (issue #158, S3).

The unit suite proves the erasure semantics and the receipt cryptography;
this contract proves the HTTP wiring: verified-credential enforcement on both
routes, the pending step erasing nothing, self-approval refused, and the
distinct-credential approval erasing one tenant and returning the signed
receipt.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.config import settings
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.services.audit_store import get_audit_store
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from tests.support.caller_credentials import (
    generate_caller_signing_key,
    mint_caller_credential,
    public_keys_setting,
)
from tests.unit.test_data_lifecycle_engine import _audit_record, _iso
from tests.unit.test_workflow_pack_run_store import _workflow_pack_run_record

_REQUESTER_KEY = generate_caller_signing_key()
_APPROVER_KEY = generate_caller_signing_key()
_PUBLIC_KEYS = public_keys_setting(
    **{"erasure-ops-alpha": _REQUESTER_KEY, "erasure-ops-beta": _APPROVER_KEY}
)
_REQUESTER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_REQUESTER_KEY,
        key_id="erasure-ops-alpha",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}
_APPROVER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_APPROVER_KEY,
        key_id="erasure-ops-beta",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caller_trust_mode", "verified_service_jwt")
    monkeypatch.setattr(settings, "caller_jwt_issuer", "https://platform.lotus/issuer")
    monkeypatch.setattr(settings, "caller_jwt_audience", "lotus-ai")
    monkeypatch.setattr(settings, "caller_jwt_public_keys", _PUBLIC_KEYS)
    signing_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", "erasure-receipt-key")
    monkeypatch.setattr(settings, "workflow_run_attestation_rotation_epoch", 1)
    monkeypatch.setattr(
        settings,
        "workflow_run_attestation_private_key_base64url",
        base64.urlsafe_b64encode(signing_key.private_bytes_raw()).rstrip(b"=").decode("ascii"),
    )
    monkeypatch.setattr(
        settings, "workflow_run_attestation_key_not_before_utc", "2026-01-01T00:00:00+00:00"
    )
    monkeypatch.setattr(
        settings, "workflow_run_attestation_key_not_after_utc", "2036-01-01T00:00:00+00:00"
    )


def test_erasure_routes_execute_the_governed_flow(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    audit = get_audit_store()
    audit.save(_audit_record("air_contract_a", tenant_id="tenant-a", days_ago=3))
    audit.save(_audit_record("air_contract_b", tenant_id="tenant-b", days_ago=3))
    runs = get_workflow_pack_run_store()
    runs.save_run(
        _workflow_pack_run_record(run_id="run_contract_b", tenant_id="tenant-b", created_at=_iso(3))
    )

    unverified = client.post(
        "/platform/data-lifecycle/erasure-requests",
        json={"tenant_id": "tenant-b", "reason": "Client off-boarding obligation."},
    )
    assert unverified.status_code == 401

    pending = client.post(
        "/platform/data-lifecycle/erasure-requests",
        json={
            "tenant_id": "tenant-b",
            "reason": "Client off-boarding obligation.",
            "requested_by": "ops.user@lotus",
        },
        headers=_REQUESTER_HEADERS,
    )
    assert pending.status_code == 200
    action = pending.json()["governed_action"]
    assert action["status"] == "PENDING"
    # Nothing is erased at the request step.
    assert len(audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=20)) == 2

    self_approval = client.post(
        "/platform/data-lifecycle/erasure-approvals",
        json={"action_id": action["action_id"], "action_hash": action["action_hash"]},
        headers=_REQUESTER_HEADERS,
    )
    assert self_approval.status_code == 403

    approved = client.post(
        "/platform/data-lifecycle/erasure-approvals",
        json={
            "action_id": action["action_id"],
            "action_hash": action["action_hash"],
            "approved_by": "second.ops@lotus",
        },
        headers=_APPROVER_HEADERS,
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["governed_action"]["status"] == "EXECUTED"
    receipt = body["receipt"]
    assert receipt["claims"]["tenant_id"] == "tenant-b"
    assert receipt["claims"]["governed_action_id"] == action["action_id"]
    assert receipt["signature"]["key_id"] == "erasure-receipt-key"
    assert receipt["signature"]["signature_base64url"]
    assert receipt["key_discovery_path"] == "/.well-known/lotus-ai-workflow-attestation-keys"
    by_family = {entry["family_id"]: entry for entry in receipt["claims"]["families"]}
    assert by_family["audit_evidence"]["erased_count"] == 1
    assert by_family["workflow_run_records"]["erased_count"] == 1

    remaining = {
        record.request_id for record in audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=20)
    }
    assert remaining == {"air_contract_a"}
    assert get_workflow_pack_run_store().list_runs() == []
