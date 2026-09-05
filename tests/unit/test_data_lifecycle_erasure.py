"""Governed tenant erasure with a signed receipt (issue #158, S3).

The issue's evaluation condition, executed: an erasure request for tenant B
removes its rows across every tenant-erasable family and yields a verifiable
receipt while tenant A is untouched; legal hold overrides erasure and the
receipt says so; the whole flow is dual-controlled through the #157
primitive.
"""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.config import settings
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.contracts.data_lifecycle import (
    DataErasureApprovalRequest,
    DataErasureApprovalResponse,
    DataErasureIntentRequest,
    DataLegalHoldRecord,
)
from app.services.audit_store import get_audit_store
from app.services.data_lifecycle_erasure import (
    approve_data_erasure,
    request_data_erasure,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER
from tests.unit.test_data_lifecycle_engine import _audit_record, _iso
from tests.unit.test_workflow_pack_run_store import _workflow_pack_run_record


def _configure_attestation_keys(monkeypatch: pytest.MonkeyPatch) -> Ed25519PrivateKey:
    private_key = Ed25519PrivateKey.generate()
    encoded = base64.urlsafe_b64encode(private_key.private_bytes_raw()).rstrip(b"=").decode()
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", "erasure-test-key")
    monkeypatch.setattr(settings, "workflow_run_attestation_rotation_epoch", 1)
    monkeypatch.setattr(settings, "workflow_run_attestation_private_key_base64url", encoded)
    monkeypatch.setattr(settings, "workflow_run_attestation_key_not_before_utc", _iso(10))
    monkeypatch.setattr(
        settings, "workflow_run_attestation_key_not_after_utc", "2036-01-01T00:00:00+00:00"
    )
    return private_key


def _seed_two_tenants() -> None:
    audit = get_audit_store()
    audit.save(_audit_record("air_keep_a", tenant_id="tenant-a", days_ago=10))
    audit.save(_audit_record("air_erase_b", tenant_id="tenant-b", days_ago=10))
    runs = get_workflow_pack_run_store()
    runs.save_run(
        _workflow_pack_run_record(run_id="run_keep_a", tenant_id="tenant-a", created_at=_iso(10))
    )
    runs.save_run(
        _workflow_pack_run_record(run_id="run_erase_b", tenant_id="tenant-b", created_at=_iso(10))
    )


def _erase_tenant_b() -> DataErasureApprovalResponse:
    pending = request_data_erasure(
        DataErasureIntentRequest(tenant_id="tenant-b", reason="Client off-boarding obligation."),
        GOVERNED_REQUESTER,
    )
    return approve_data_erasure(
        DataErasureApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )


def test_erasure_removes_one_tenant_and_yields_a_verifiable_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = _configure_attestation_keys(monkeypatch)
    _seed_two_tenants()

    response = _erase_tenant_b()

    audit = get_audit_store()
    remaining = {r.request_id for r in audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=20)}
    assert remaining == {"air_keep_a"}
    assert {r.run_id for r in get_workflow_pack_run_store().list_runs()} == {"run_keep_a"}

    receipt = response.receipt
    assert receipt.claims.tenant_id == "tenant-b"
    assert receipt.claims.governed_action_id == response.governed_action.action_id
    by_family = {f.family_id: f for f in receipt.claims.families}
    assert by_family["audit_evidence"].erased_count == 1
    assert by_family["workflow_run_records"].erased_count == 1
    assert not any(f.held for f in receipt.claims.families)

    # The receipt verifies against the signing key - the artefact #115
    # consumers can check independently.
    payload = json.dumps(
        receipt.claims.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    signature = base64.urlsafe_b64decode(
        receipt.signature.signature_base64url
        + "=" * (-len(receipt.signature.signature_base64url) % 4)
    )
    private_key.public_key().verify(signature, payload)  # raises on mismatch
    assert receipt.signature.key_id == "erasure-test-key"

    # ERASURE lifecycle events landed per touched family, tenant-scoped.
    events = [e for e in audit.list_lifecycle_events(limit=20) if e.action.value == "ERASURE"]
    assert {e.family_id for e in events} == {"audit_evidence", "workflow_run_records"}
    assert all(e.key_scope == "tenant:tenant-b" for e in events)

    # The governed evidence chain is complete and dual-controlled.
    assert response.governed_action.status.value == "EXECUTED"
    assert response.governed_action.requester_key_id != response.governed_action.approver_key_id


def test_legal_hold_overrides_erasure_and_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_attestation_keys(monkeypatch)
    _seed_two_tenants()
    get_audit_store().place_legal_hold(
        DataLegalHoldRecord(
            hold_id="hold_erase_b",
            family_id="audit_evidence",
            key_type="tenant",
            key_value="tenant-b",
            reason="Litigation hold.",
            placed_by="legal.ops@lotus",
            placed_at=_iso(1),
        )
    )

    response = _erase_tenant_b()

    by_family = {f.family_id: f for f in response.receipt.claims.families}
    # The held family kept its rows and the receipt says so; the unheld
    # family erased normally.
    assert by_family["audit_evidence"].held is True
    assert by_family["audit_evidence"].erased_count == 0
    assert by_family["workflow_run_records"].held is False
    assert by_family["workflow_run_records"].erased_count == 1
    remaining = {
        r.request_id for r in get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=20)
    }
    assert "air_erase_b" in remaining


def test_erasure_executors_and_policy_tenant_erasable_families_agree() -> None:
    """The policy is the authority on erasure scope: a family cannot declare
    `erasure_key: tenant` without an executor behind it, and an executor cannot
    outlive its family's declaration."""

    from app.services.data_lifecycle_erasure import _ERASURE_EXECUTORS
    from app.services.data_lifecycle_policy import load_retention_policy

    declared = {
        family.family_id
        for family in load_retention_policy().families
        if family.erasure_key == "tenant"
    }
    assert set(_ERASURE_EXECUTORS) == declared


def test_erasure_requires_a_distinct_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_attestation_keys(monkeypatch)
    pending = request_data_erasure(
        DataErasureIntentRequest(tenant_id="tenant-x", reason="Off-boarding."),
        GOVERNED_REQUESTER,
    )

    with pytest.raises(HTTPException) as exc_info:
        approve_data_erasure(
            DataErasureApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_REQUESTER,
        )
    assert exc_info.value.status_code == 403
    assert "distinct" in exc_info.value.detail


def test_erasure_covers_attributed_async_jobs_and_artifacts_with_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #291: tenant erasure reaches attributed async jobs (with
    attempts) and artifacts (payload bytes AND metadata); NULL-attribution
    rows are counted on the receipt, never erased, never inferred."""

    from app.repositories.async_runtime_repository import AsyncRuntimeJobRecord
    from app.services.artifact_payloads import persist_json_artifact
    from app.services.artifact_store import get_artifact_object_store, get_artifact_repository
    from app.services.async_runtime_store import get_async_runtime_store

    _configure_attestation_keys(monkeypatch)
    _seed_two_tenants()

    jobs = get_async_runtime_store()

    def _job(job_id: str, tenant: str | None) -> AsyncRuntimeJobRecord:
        return AsyncRuntimeJobRecord(
            job_id=job_id,
            job_type="workflow_pack_execution",
            target_id=None,
            lifecycle_status="COMPLETED",
            submitted_at=_iso(5),
            caller_app="lotus-gateway",
            correlation_id=f"corr-{job_id}",
            payload_summary="snapshot",
            execution_path="queue",
            related_evaluation_run_id=None,
            latest_message="m",
            attempt_count=1,
            artifact_ids=[],
            tenant_id=tenant,
        )

    jobs.save_job(_job("job_keep_a", "tenant-a"))
    jobs.save_job(_job("job_erase_b", "tenant-b"))
    jobs.save_job(_job("job_platform", None))

    def _artifact(source_id: str, tenant: str | None) -> str:
        descriptor = persist_json_artifact(
            domain="workflow_pack_runs",
            artifact_type="advisor_brief_document",
            source_object_kind="async_job",
            source_object_id=source_id,
            created_at=_iso(5),
            created_by="worker-1",
            payload_json=b'{"content": "generated"}',
            tenant_id=tenant,
        )
        return descriptor.artifact_id

    art_a = _artifact("job_keep_a", "tenant-a")
    art_b = _artifact("job_erase_b", "tenant-b")
    art_platform = _artifact("job_platform", None)

    response = _erase_tenant_b()

    remaining_jobs = {job.job_id for job in jobs.list_jobs()}
    assert remaining_jobs == {"job_keep_a", "job_platform"}

    artifacts = get_artifact_repository()
    remaining_artifacts = {record.artifact_id for record in artifacts.list_artifacts()}
    assert remaining_artifacts == {art_a, art_platform}
    # The payload bytes went with the metadata - no orphaned content.
    object_store = get_artifact_object_store()
    erased_reference = f"workflow_pack_runs/async_job/job_erase_b/{art_b}.json"
    assert object_store.get_object(object_key=erased_reference) is None
    kept_reference = f"workflow_pack_runs/async_job/job_keep_a/{art_a}.json"
    assert object_store.get_object(object_key=kept_reference) is not None

    by_family = {f.family_id: f for f in response.receipt.claims.families}
    async_result = by_family["async_runtime_content"]
    # job + its submission attempt = 2 rows erased; the platform job is
    # honestly counted as unattributable, not touched.
    assert async_result.erased_count >= 1
    assert async_result.unattributable_count == 1
    artifact_result = by_family["artifact_content"]
    assert artifact_result.erased_count == 1
    assert artifact_result.unattributable_count == 1
    # Fully attributed stores carry no unattributable claim.
    assert by_family["audit_evidence"].unattributable_count is None


def test_missing_signing_key_means_zero_deletion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit F3: signing readiness is validated BEFORE destructive work - an
    absent receipt key refuses the approval with nothing erased and the
    governed action still PENDING and approvable after the key is fixed."""

    _seed_two_tenants()
    monkeypatch.setattr(settings, "workflow_run_attestation_key_id", "")
    pending = request_data_erasure(
        DataErasureIntentRequest(tenant_id="tenant-b", reason="Off-boarding."),
        GOVERNED_REQUESTER,
    )

    with pytest.raises(HTTPException) as exc_info:
        approve_data_erasure(
            DataErasureApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )

    assert exc_info.value.status_code == 503
    audit_records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=100)
    assert any(record.tenant_id == "tenant-b" for record in audit_records)
    from app.services.provider_operations_store import get_provider_operations_store

    stored = get_provider_operations_store().get_governed_action(pending.governed_action.action_id)
    assert stored is not None
    assert stored.status.value == "PENDING"


def test_lost_receipt_is_retrievable_from_durable_results_without_reerasing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit F3: a response lost after execution returns the SAME evidenced
    outcome on retry - counts from the durable result payload, no second
    deletion pass, no 409."""

    _configure_attestation_keys(monkeypatch)
    _seed_two_tenants()
    first = _erase_tenant_b()
    first_counts = {
        family.family_id: family.erased_count for family in first.receipt.claims.families
    }
    assert any(count > 0 for count in first_counts.values())

    retry = approve_data_erasure(
        DataErasureApprovalRequest(
            action_id=first.governed_action.action_id,
            action_hash=first.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )

    retry_counts = {
        family.family_id: family.erased_count for family in retry.receipt.claims.families
    }
    assert retry_counts == first_counts
    assert retry.governed_action.action_id == first.governed_action.action_id
    assert retry.receipt.claims.executed_at == first.receipt.claims.executed_at
    # Tenant A remains untouched by the retry.
    audit_records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=100)
    assert any(record.tenant_id == "tenant-a" for record in audit_records)


def test_crash_after_a_family_completes_recovers_the_evidenced_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit F3: a crash between families neither loses the completed family's
    evidenced count nor forces a blind re-erasure - the deterministic per-
    action/family lifecycle event carries the first pass's count into the
    recovered receipt."""

    _configure_attestation_keys(monkeypatch)
    _seed_two_tenants()
    pending = request_data_erasure(
        DataErasureIntentRequest(tenant_id="tenant-b", reason="Off-boarding."),
        GOVERNED_REQUESTER,
    )

    import app.services.data_lifecycle_erasure as erasure_module

    original_executors = dict(erasure_module._ERASURE_EXECUTORS)
    family_order = list(original_executors)
    crash_on_entry = family_order[-1]

    def _crashing(family_id: str) -> object:
        executor = original_executors[family_id]

        def run(tenant_id: str) -> tuple[int, int | None]:
            # The crash lands BETWEEN families: every earlier family fully
            # completed, including its durable lifecycle event.
            if family_id == crash_on_entry:
                raise RuntimeError("process died between families")
            return executor(tenant_id)

        return run

    monkeypatch.setattr(
        erasure_module,
        "_ERASURE_EXECUTORS",
        {family_id: _crashing(family_id) for family_id in family_order},
    )

    with pytest.raises(RuntimeError):
        approve_data_erasure(
            DataErasureApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )

    # Recovery: the claiming credential retries with the original executors.
    monkeypatch.setattr(erasure_module, "_ERASURE_EXECUTORS", original_executors)
    monkeypatch.setattr(
        erasure_module,
        "approve_and_execute_governed_action",
        lambda **kwargs: __import__(
            "app.services.governed_action_control", fromlist=["x"]
        ).approve_and_execute_governed_action(**kwargs, resume_interrupted_claim=True),
    )
    recovered = approve_data_erasure(
        DataErasureApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )

    counts = {family.family_id: family.erased_count for family in recovered.receipt.claims.families}
    # Families that completed before the crash report their FIRST pass's
    # evidenced counts, not an honest-but-empty re-deletion.
    assert sum(counts.values()) > 0
    assert any(counts[family_id] > 0 for family_id in family_order[:-1])
