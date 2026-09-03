"""Governed tenant erasure with a signed receipt (issue #158, S3).

Erasure permanently destroys client-derived rows across every tenant-erasable
family, so it composes the #157 governed-action primitive: a verified
requester states the intent, a distinct verified credential approves the
exact hash, and the execution writes one ERASURE lifecycle event per touched
family and issues an Ed25519-signed receipt #115 consumers can verify against
the published attestation keys.

Legal hold overrides erasure: a held family is listed on the receipt with
``held=true`` and zero erasures - recorded, never silently skipped. Erasure
overrides retention (rows go regardless of age); both rules are the issue's
own invariants.
"""

from __future__ import annotations

import hashlib
import json
from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.audit_access import AuditReadScope
from app.contracts.data_lifecycle import (
    DataErasureApprovalRequest,
    DataErasureApprovalResponse,
    DataErasureFamilyResult,
    DataErasureIntentRequest,
    DataErasureReceiptClaims,
    DataErasureReceiptEnvelope,
    DataLifecycleAction,
    DataLifecycleEventRecord,
)
from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionType,
)
from app.contracts.workflow_run_attestation import WorkflowRunAttestationSignature
from app.http.authenticated_caller import AuthenticatedCaller
from app.providers.configured_workflow_run_attestation_keys import (
    ConfiguredWorkflowRunAttestationKeys,
)
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.audit_store import get_audit_store
from app.services.data_lifecycle_policy import load_retention_policy
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_queue_event_store import get_workflow_pack_queue_event_store
from app.services.workflow_pack_task_flow_store import get_workflow_pack_task_flow_store
from app.workflow_pack_execution_idempotency.store import (
    get_workflow_pack_execution_idempotency_store,
)

_ERASURE_BATCH_LIMIT = 5000


def _require_provider_control_authorization(caller: AuthenticatedCaller) -> None:
    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )


def _tenant_erasable_family_ids() -> list[str]:
    return [
        family.family_id
        for family in load_retention_policy().families
        if family.erasure_key == "tenant"
    ]


def _erasure_payload(*, tenant_id: str, reason: str) -> dict[str, str | None]:
    """The exact action the approver signs off on.

    Pins the tenant, the reason, and the family set in scope at request time:
    an approval reviewed against one erasure scope must not execute against
    another (a policy change between request and approval refuses).
    """

    return {
        "action_type": GovernedActionType.DATA_ERASURE.value,
        "tenant_id": tenant_id,
        "reason": reason,
        "families": ",".join(sorted(_tenant_erasable_family_ids())),
    }


def request_data_erasure(
    request: DataErasureIntentRequest, caller: AuthenticatedCaller
) -> GovernedActionResponse:
    """Step one: record the erasure intent under the requester's credential."""

    _require_provider_control_authorization(caller)
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.DATA_ERASURE,
        target=request.tenant_id,
        payload=_erasure_payload(tenant_id=request.tenant_id, reason=request.reason),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Erasure of tenant `{request.tenant_id}` across families "
            f"{sorted(_tenant_erasable_family_ids())} is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            "Nothing is erased until the approval executes; active legal holds "
            "will keep their families untouched and the receipt will say so.",
        ],
    )


def approve_data_erasure(
    request: DataErasureApprovalRequest, caller: AuthenticatedCaller
) -> DataErasureApprovalResponse:
    """Step two: a distinct verified credential approves; execution erases,
    evidences and issues the signed receipt."""

    _require_provider_control_authorization(caller)
    outcome: dict[str, object] = {}

    def _execute_erasure(record: GovernedActionRecord) -> None:
        tenant_id = str(record.action_payload.get("tenant_id"))
        now = datetime.now(UTC).isoformat()
        results: list[DataErasureFamilyResult] = []
        for family_id in _tenant_erasable_family_ids():
            held = any(
                hold.key_type == "tenant" and hold.key_value == tenant_id
                for hold in get_audit_store().list_active_legal_holds(family_id=family_id)
            )
            if held:
                results.append(
                    DataErasureFamilyResult(family_id=family_id, erased_count=0, held=True)
                )
                continue
            erased = _ERASURE_EXECUTORS[family_id](tenant_id)
            results.append(
                DataErasureFamilyResult(family_id=family_id, erased_count=erased, held=False)
            )
            if erased:
                get_audit_store().save_lifecycle_event(
                    DataLifecycleEventRecord(
                        event_id=f"dle_{uuid4().hex[:16]}",
                        family_id=family_id,
                        action=DataLifecycleAction.ERASURE,
                        key_scope=f"tenant:{tenant_id}",
                        row_count=erased,
                        policy_version=load_retention_policy().policy_version,
                        actor=f"{caller.caller_app} (credential {caller.credential_key_id})",
                        deleted_ids_digest=hashlib.sha256(
                            f"{family_id}:{tenant_id}:{erased}:{now}".encode("utf-8")
                        ).hexdigest(),
                        recorded_at=now,
                    )
                )
        outcome["results"] = results
        outcome["executed_at"] = now

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=_expected_target(request),
        expected_hash=request.action_hash,
        current_payload_builder=lambda record: _erasure_payload(
            tenant_id=str(record.action_payload.get("tenant_id")),
            reason=str(record.action_payload.get("reason")),
        ),
        attribution=request.approved_by,
        execute=_execute_erasure,
    )
    results = outcome["results"]
    assert isinstance(results, list)
    receipt = _issue_receipt(
        tenant_id=executed.target,
        reason=str(executed.action_payload.get("reason")),
        governed_action_id=executed.action_id,
        families=results,
        executed_at=str(outcome["executed_at"]),
    )
    return DataErasureApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        receipt=receipt,
        governed_action=executed,
        summary=[
            f"Erased tenant `{executed.target}` under governed action `{executed.action_id}`.",
            f"Requested under credential `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}`.",
            "Held families are listed on the receipt with held=true; the receipt "
            "signature verifies against the published attestation keys.",
        ],
    )


def _expected_target(request: DataErasureApprovalRequest) -> str:
    """The approver approves the pending action wherever it targets; the hash
    binds the exact tenant, so the target check re-derives from the store."""

    from app.services.provider_operations_store import get_provider_operations_store

    record = get_provider_operations_store().get_governed_action(request.action_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed action exists for `{request.action_id}`.",
        )
    return record.target


def _erase_audit_evidence(tenant_id: str) -> int:
    repository = get_audit_store()
    erased = 0
    while True:
        records = repository.list(
            scope=AuditReadScope.restricted(frozenset({tenant_id})),
            limit=_ERASURE_BATCH_LIMIT,
        )
        if not records:
            return erased
        erased += repository.delete_records([record.request_id for record in records])


def _erase_workflow_run_records(tenant_id: str) -> int:
    """Erasure must be exhaustive - the receipt claims completeness - so every
    scan here is unbounded, unlike expiry's bounded batches (which self-heal on
    the next scheduled run)."""

    erased = 0
    runs = get_workflow_pack_run_store()
    run_ids = [record.run_id for record in runs.list_runs() if record.tenant_id == tenant_id]
    if run_ids:
        run_count, event_count = runs.delete_runs_with_events(run_ids)
        erased += run_count + event_count
    flows = get_workflow_pack_task_flow_store()
    flow_ids = [
        record.descriptor.task_flow_id
        for record in flows.list_task_flows()
        if record.descriptor.tenant_id == tenant_id
    ]
    if flow_ids:
        flow_count, checkpoint_count = flows.delete_task_flows_with_checkpoints(flow_ids)
        erased += flow_count + checkpoint_count
    queue_events = get_workflow_pack_queue_event_store()
    event_ids = [
        record.descriptor.event_id
        for record in queue_events.list_events(limit=None)
        if record.descriptor.tenant_id == tenant_id
    ]
    if event_ids:
        erased += queue_events.delete_events(event_ids)
    idempotency = get_workflow_pack_execution_idempotency_store()
    record_ids = [
        record.record_id
        for record in idempotency.list_records(limit=None)
        if record.tenant_scope == tenant_id
    ]
    if record_ids:
        erased += idempotency.delete_records(record_ids)
    return erased


_ERASURE_EXECUTORS = {
    "audit_evidence": _erase_audit_evidence,
    "workflow_run_records": _erase_workflow_run_records,
}


def _issue_receipt(
    *,
    tenant_id: str,
    reason: str,
    governed_action_id: str,
    families: list[DataErasureFamilyResult],
    executed_at: str,
) -> DataErasureReceiptEnvelope:
    claims = DataErasureReceiptClaims(
        schema_version="lotus-ai.data-erasure-receipt.v1",
        issuer="lotus-ai",
        receipt_id=f"der_{uuid4().hex[:16]}",
        tenant_id=tenant_id,
        reason=reason,
        policy_version=load_retention_policy().policy_version,
        governed_action_id=governed_action_id,
        families=families,
        executed_at=executed_at,
    )
    payload = json.dumps(
        claims.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    signer = ConfiguredWorkflowRunAttestationKeys(settings=settings).signer()
    signed = signer.sign(payload)
    return DataErasureReceiptEnvelope(
        claims=claims,
        signature=WorkflowRunAttestationSignature(
            algorithm=signed.algorithm,
            key_id=signed.key_id,
            rotation_epoch=signed.rotation_epoch,
            signature_base64url=urlsafe_b64encode(signed.signature).rstrip(b"=").decode("ascii"),
        ),
        key_discovery_path="/.well-known/lotus-ai-workflow-attestation-keys",
    )
