from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueRecoveryActionType,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunRecoveryActionType,
    WorkflowPackRunRecoveryLineageDescriptor,
)
from app.contracts.workflow_pack_queue_recovery import (
    WorkflowPackQueueRecoveryExecutionResponse,
)
from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.http.authenticated_caller import bind_internal_authenticated_caller
from app.services.artifact_payloads import persist_json_artifact
from app.services.artifact_store import get_artifact_object_store, get_artifact_repository
from app.services.workflow_pack_execution import execute_workflow_pack
from app.services.workflow_pack_queue_events import build_workflow_pack_queue_event_detail
from app.services.workflow_pack_queue_recovery import (
    authorize_workflow_pack_queue_recovery_caller,
    get_workflow_pack_queue_recovery_source_event,
    record_workflow_pack_queue_replay_decision,
    record_workflow_pack_queue_retry_decision,
)
from app.services.workflow_pack_queue_request_snapshots import (
    build_workflow_pack_execution_request_from_queue_snapshot,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store

QUEUE_RECOVERY_EXECUTION_RESPONSE_ARTIFACT_TYPE = "queue_recovery_execution_response"


def execute_workflow_pack_queue_retry(
    *,
    queue_item_id: str,
    caller_app: str,
    failure_code: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
    idempotency_key: str | None = None,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    authorize_workflow_pack_queue_recovery_caller(caller_app=caller_app)
    source_event = get_workflow_pack_queue_recovery_source_event(queue_item_id=queue_item_id)
    execution_request = _build_execution_request(source_event=source_event)
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    request_fingerprint = _fingerprint_recovery_execution_command(
        queue_item_id=queue_item_id,
        action_type=WorkflowPackQueueRecoveryActionType.RETRY,
        caller_app=caller_app,
        failure_code=failure_code,
        requested_by=requested_by,
        reason=reason,
        evidence_ref=evidence_ref,
    )
    if normalized_idempotency_key is not None:
        existing_response = _resolve_existing_recovery_execution_response(
            queue_item_id=queue_item_id,
            action_type=WorkflowPackQueueRecoveryActionType.RETRY,
            idempotency_key=normalized_idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if existing_response is not None:
            return existing_response
    event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
        caller_app=caller_app,
        failure_code=failure_code,
        requested_by=requested_by,
        reason=reason,
        evidence_ref=evidence_ref,
        idempotency_key=normalized_idempotency_key,
        idempotency_request_fingerprint=request_fingerprint,
    )
    if event.event_type is not WorkflowPackQueueEventType.RETRY_RECORDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue retry execution was not started because retry was blocked "
                f"by policy. Blocking event: {event.event_id}."
            ),
        )
    with bind_internal_authenticated_caller(
        caller_app=execution_request.task_request.caller.caller_app,
        trust_source="retained_queue_request_snapshot",
    ):
        execution = execute_workflow_pack(
            execution_request,
            recovery_lineage=_build_recovery_lineage(
                source_event=source_event,
                decision_event=event,
                action_type=WorkflowPackRunRecoveryActionType.RETRY,
            ),
        )
    response = WorkflowPackQueueRecoveryExecutionResponse(
        service=execution.service,
        version=execution.version,
        phase=settings.delivery_phase,
        decision_event=event,
        execution=execution,
        idempotency_key=normalized_idempotency_key,
        idempotency_status="CREATED" if normalized_idempotency_key is not None else None,
        status_summary=[
            "Workflow-pack queue retry decision was recorded and executed from the retained request snapshot.",
            "The retry execution used the normal workflow-pack execution path, including eligibility, queue admission, run ledger, and task-flow recording.",
        ],
    )
    _persist_recovery_execution_response(
        response=response,
        queue_item_id=queue_item_id,
        action_type=WorkflowPackQueueRecoveryActionType.RETRY,
        idempotency_key=normalized_idempotency_key,
    )
    return response


def execute_workflow_pack_queue_replay(
    *,
    queue_item_id: str,
    caller_app: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
    idempotency_key: str | None = None,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    authorize_workflow_pack_queue_recovery_caller(caller_app=caller_app)
    source_event = get_workflow_pack_queue_recovery_source_event(queue_item_id=queue_item_id)
    execution_request = _build_execution_request(source_event=source_event)
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    request_fingerprint = _fingerprint_recovery_execution_command(
        queue_item_id=queue_item_id,
        action_type=WorkflowPackQueueRecoveryActionType.REPLAY,
        caller_app=caller_app,
        failure_code=None,
        requested_by=requested_by,
        reason=reason,
        evidence_ref=evidence_ref,
    )
    if normalized_idempotency_key is not None:
        existing_response = _resolve_existing_recovery_execution_response(
            queue_item_id=queue_item_id,
            action_type=WorkflowPackQueueRecoveryActionType.REPLAY,
            idempotency_key=normalized_idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if existing_response is not None:
            return existing_response
    event = record_workflow_pack_queue_replay_decision(
        queue_item_id=queue_item_id,
        caller_app=caller_app,
        requested_by=requested_by,
        reason=reason,
        evidence_ref=evidence_ref,
        idempotency_key=normalized_idempotency_key,
        idempotency_request_fingerprint=request_fingerprint,
    )
    if event.event_type is not WorkflowPackQueueEventType.REPLAY_RECORDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue replay execution was not started because replay was blocked "
                f"by policy. Blocking event: {event.event_id}."
            ),
        )
    with bind_internal_authenticated_caller(
        caller_app=execution_request.task_request.caller.caller_app,
        trust_source="retained_queue_request_snapshot",
    ):
        execution = execute_workflow_pack(
            execution_request,
            recovery_lineage=_build_recovery_lineage(
                source_event=source_event,
                decision_event=event,
                action_type=WorkflowPackRunRecoveryActionType.REPLAY,
            ),
        )
    response = WorkflowPackQueueRecoveryExecutionResponse(
        service=execution.service,
        version=execution.version,
        phase=settings.delivery_phase,
        decision_event=event,
        execution=execution,
        idempotency_key=normalized_idempotency_key,
        idempotency_status="CREATED" if normalized_idempotency_key is not None else None,
        status_summary=[
            "Workflow-pack queue replay decision was recorded and executed from the retained request snapshot.",
            "The replay execution used the normal workflow-pack execution path, including eligibility, queue admission, run ledger, and task-flow recording.",
        ],
    )
    _persist_recovery_execution_response(
        response=response,
        queue_item_id=queue_item_id,
        action_type=WorkflowPackQueueRecoveryActionType.REPLAY,
        idempotency_key=normalized_idempotency_key,
    )
    return response


def _resolve_existing_recovery_execution_response(
    *,
    queue_item_id: str,
    action_type: WorkflowPackQueueRecoveryActionType,
    idempotency_key: str,
    request_fingerprint: str,
) -> WorkflowPackQueueRecoveryExecutionResponse | None:
    history = build_workflow_pack_queue_event_detail(queue_item_id=queue_item_id).events
    matching_events = [
        event
        for event in history
        if event.recovery_action_type == action_type and event.idempotency_key == idempotency_key
    ]
    if not matching_events:
        return None
    event = matching_events[0]
    if event.idempotency_request_fingerprint != request_fingerprint:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue recovery idempotency conflict: idempotency key "
                f"`{idempotency_key}` was reused with different {action_type.value.lower()} input "
                f"for queue item `{queue_item_id}`."
            ),
        )
    response = _load_recovery_execution_response(
        queue_item_id=queue_item_id,
        action_type=action_type,
        idempotency_key=idempotency_key,
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue recovery idempotency result is not yet available for "
                f"key `{idempotency_key}` on queue item `{queue_item_id}`."
            ),
        )
    return response.model_copy(
        update={
            "idempotency_status": "REPLAYED",
            "status_summary": [
                *response.status_summary,
                (
                    "Workflow-pack queue recovery execution reused the first retained response "
                    "for the same idempotent operator command; no duplicate run was created."
                ),
            ],
        },
        deep=True,
    )


def _persist_recovery_execution_response(
    *,
    response: WorkflowPackQueueRecoveryExecutionResponse,
    queue_item_id: str,
    action_type: WorkflowPackQueueRecoveryActionType,
    idempotency_key: str | None,
) -> None:
    if idempotency_key is None:
        return
    persist_json_artifact(
        domain="workflow_pack",
        artifact_type=QUEUE_RECOVERY_EXECUTION_RESPONSE_ARTIFACT_TYPE,
        source_object_kind="workflow_pack_queue_recovery_execution",
        source_object_id=_recovery_execution_response_source_id(
            queue_item_id=queue_item_id,
            action_type=action_type,
            idempotency_key=idempotency_key,
        ),
        created_at=response.decision_event.recorded_at,
        created_by="lotus-ai.workflow-pack-queue-recovery",
        payload_json=response.model_dump_json().encode("utf-8"),
        retention_posture="retained_for_idempotent_replay",
    )


def _load_recovery_execution_response(
    *,
    queue_item_id: str,
    action_type: WorkflowPackQueueRecoveryActionType,
    idempotency_key: str,
) -> WorkflowPackQueueRecoveryExecutionResponse | None:
    source_object_id = _recovery_execution_response_source_id(
        queue_item_id=queue_item_id,
        action_type=action_type,
        idempotency_key=idempotency_key,
    )
    matches = [
        artifact
        for artifact in get_artifact_repository().list_artifacts()
        if artifact.domain == "workflow_pack"
        and artifact.artifact_type == QUEUE_RECOVERY_EXECUTION_RESPONSE_ARTIFACT_TYPE
        and artifact.source_object_kind == "workflow_pack_queue_recovery_execution"
        and artifact.source_object_id == source_object_id
        and artifact.superseded_by_artifact_id is None
    ]
    if not matches:
        return None
    artifact = matches[-1]
    object_key = _parse_storage_reference(artifact.storage_reference)
    stored_object = get_artifact_object_store().get_object(object_key=object_key)
    if stored_object is None:
        return None
    if hashlib.sha256(stored_object.payload).hexdigest() != artifact.checksum_sha256:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow-pack queue recovery idempotency response checksum does not match.",
        )
    return WorkflowPackQueueRecoveryExecutionResponse.model_validate(
        json.loads(stored_object.payload)
    )


def _fingerprint_recovery_execution_command(
    *,
    queue_item_id: str,
    action_type: WorkflowPackQueueRecoveryActionType,
    caller_app: str,
    failure_code: str | None,
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> str:
    payload = {
        "queue_item_id": queue_item_id,
        "action_type": action_type.value,
        "caller_app": caller_app,
        "failure_code": failure_code,
        "requested_by": requested_by,
        "reason": reason,
        "evidence_ref": evidence_ref,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _recovery_execution_response_source_id(
    *,
    queue_item_id: str,
    action_type: WorkflowPackQueueRecoveryActionType,
    idempotency_key: str,
) -> str:
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
    return f"{queue_item_id}-{action_type.value.lower()}-{key_hash}"


def _normalize_idempotency_key(idempotency_key: str | None) -> str | None:
    if idempotency_key is None:
        return None
    normalized = idempotency_key.strip()
    return normalized or None


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )


def _parse_storage_reference(storage_reference: str) -> str:
    _, _, object_key = storage_reference.partition("://")
    return object_key


def _build_execution_request(
    *, source_event: WorkflowPackQueueEventDescriptor
) -> WorkflowPackExecutionRequest:
    try:
        return build_workflow_pack_execution_request_from_queue_snapshot(source_event=source_event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _build_recovery_lineage(
    *,
    source_event: WorkflowPackQueueEventDescriptor,
    decision_event: WorkflowPackQueueEventDescriptor,
    action_type: WorkflowPackRunRecoveryActionType,
) -> WorkflowPackRunRecoveryLineageDescriptor:
    return WorkflowPackRunRecoveryLineageDescriptor(
        recovery_action_type=action_type,
        source_queue_item_id=source_event.queue_item_id,
        recovery_decision_event_id=decision_event.event_id,
        recovery_attempt_number=decision_event.recovery_attempt_number,
        source_workflow_pack_run_id=_resolve_source_workflow_pack_run_id(source_event),
        requested_by=decision_event.requested_by,
        evidence_ref=decision_event.evidence_ref,
    )


def _resolve_source_workflow_pack_run_id(
    source_event: WorkflowPackQueueEventDescriptor,
) -> str | None:
    if source_event.correlation_id is None:
        return None
    candidates = get_workflow_pack_run_store().query_runs(
        pack_id=source_event.workflow_pack_id,
        caller_app=source_event.caller_app,
        tenant_id=source_event.tenant_id,
        workflow_surface=source_event.workflow_surface,
        limit=20,
    )
    for candidate in candidates:
        if candidate.correlation_id == source_event.correlation_id:
            return candidate.run_id
    return None
