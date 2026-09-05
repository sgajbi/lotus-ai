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
from typing import cast
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
    GovernedActionStatus,
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
from app.services.provider_operations_store import get_provider_operations_store
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
    # Signing readiness BEFORE destructive work (issue #327/F3): a missing or
    # malformed receipt key must mean ZERO deletion, not an unreceipted one.
    try:
        ConfiguredWorkflowRunAttestationKeys(settings=settings).signer()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The erasure-receipt signing key is not available; nothing was "
                "erased. Configure the attestation signing material and retry."
            ),
        ) from exc

    # A lost response is recoverable without re-erasing: an EXECUTED action
    # with the same hash returns the SAME evidenced outcome, re-signed from
    # the durable result payload.
    existing = get_provider_operations_store().get_governed_action(request.action_id)
    if (
        existing is not None
        and existing.status is GovernedActionStatus.EXECUTED
        and existing.action_hash == request.action_hash
        and existing.result_payload is not None
    ):
        return _erasure_response_from_result(existing)

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
            erased, unattributable = _ERASURE_EXECUTORS[family_id](tenant_id)
            # Deterministic per-action/family evidence id (issue #327): a
            # recovery re-run after a crash merges the first pass's durable
            # count instead of reporting an honest-but-empty re-deletion.
            event_id = _family_erasure_event_id(record.action_id, family_id)
            prior_event = next(
                (
                    event
                    for event in get_audit_store().list_lifecycle_events(limit=10000)
                    if event.event_id == event_id
                ),
                None,
            )
            if prior_event is not None:
                erased = max(erased, prior_event.row_count)
            results.append(
                DataErasureFamilyResult(
                    family_id=family_id,
                    erased_count=erased,
                    held=False,
                    unattributable_count=unattributable,
                )
            )
            if erased:
                get_audit_store().save_lifecycle_event(
                    DataLifecycleEventRecord(
                        event_id=event_id,
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
        result_payload_builder=lambda: {
            "results": [
                result.model_dump(mode="json")
                for result in cast(list[DataErasureFamilyResult], outcome["results"])
            ],
            "executed_at": outcome["executed_at"],
        },
        resume_interrupted_claim=request.resume_interrupted_claim,
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


def _family_erasure_event_id(action_id: str, family_id: str) -> str:
    digest = hashlib.sha256(f"{action_id}:{family_id}".encode("utf-8")).hexdigest()[:24]
    return f"dle_{digest}"


def _erasure_response_from_result(record: GovernedActionRecord) -> DataErasureApprovalResponse:
    """Rebuild the evidenced erasure outcome from the durable result payload.

    Re-signing the same claims is retrieval, not re-erasure: the counts,
    families and execution instant are exactly the ones the executed action
    recorded (issue #327/F3).
    """

    payload = record.result_payload or {}
    raw_results = payload.get("results")
    results = [
        DataErasureFamilyResult.model_validate(item)
        for item in (raw_results if isinstance(raw_results, list) else [])
    ]
    receipt = _issue_receipt(
        tenant_id=record.target,
        reason=str(record.action_payload.get("reason")),
        governed_action_id=record.action_id,
        families=results,
        executed_at=str(payload.get("executed_at")),
    )
    return DataErasureApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        receipt=receipt,
        governed_action=record,
        summary=[
            f"Erasure of tenant `{record.target}` under governed action "
            f"`{record.action_id}` was already executed; this is the evidenced "
            "outcome re-signed from durable results, not a re-erasure.",
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


def _erase_audit_evidence(tenant_id: str) -> tuple[int, int | None]:
    repository = get_audit_store()
    erased = 0
    while True:
        records = repository.list(
            scope=AuditReadScope.restricted(frozenset({tenant_id})),
            limit=_ERASURE_BATCH_LIMIT,
        )
        if not records:
            return erased, None
        erased += repository.delete_records([record.request_id for record in records])


def _erase_workflow_run_records(tenant_id: str) -> tuple[int, int | None]:
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
    return erased, None


def _erase_async_runtime_content(tenant_id: str) -> tuple[int, int | None]:
    """Attributed async jobs (with attempts and leases) for one tenant
    (issue #291); NULL-attribution rows are counted honestly, never erased,
    never inferred - they leave only by the family's own expiry."""

    from app.services.async_runtime_store import get_async_runtime_store

    store = get_async_runtime_store()
    jobs = store.list_jobs()
    mine = [job.job_id for job in jobs if job.tenant_id == tenant_id]
    unattributable = sum(1 for job in jobs if job.tenant_id is None)
    if not mine:
        return 0, unattributable
    deleted_jobs, deleted_attempts, deleted_leases = store.delete_job_records(mine)
    return deleted_jobs + deleted_attempts + deleted_leases, unattributable


def _erase_artifact_content(tenant_id: str) -> tuple[int, int | None]:
    """Attributed artifacts for one tenant, payload bytes and metadata
    together (issue #291); NULL-attribution rows are counted, never erased."""

    from app.services.artifact_payloads import delete_artifacts_with_payloads
    from app.services.artifact_store import get_artifact_repository

    records = get_artifact_repository().list_artifacts()
    mine = [record for record in records if record.tenant_id == tenant_id]
    unattributable = sum(1 for record in records if record.tenant_id is None)
    if not mine:
        return 0, unattributable
    return delete_artifacts_with_payloads(mine), unattributable


_ERASURE_EXECUTORS = {
    "audit_evidence": _erase_audit_evidence,
    "workflow_run_records": _erase_workflow_run_records,
    "async_runtime_content": _erase_async_runtime_content,
    "artifact_content": _erase_artifact_content,
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
