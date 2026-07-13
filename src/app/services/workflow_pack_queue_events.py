from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.config import settings
from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventCatalogResponse,
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventDetailResponse,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueueRecoveryActionType,
    WorkflowPackQueueState,
)
from app.repositories.workflow_pack_queue_event_repository import (
    WorkflowPackQueueEventRecord,
)
from app.services.runtime_readiness import (
    get_workflow_pack_queue_event_store_runtime_status,
)
from app.services.workflow_pack_queue_event_store import get_workflow_pack_queue_event_store


class WorkflowPackQueueEventStoreNotReadyError(RuntimeError):
    pass


def ensure_workflow_pack_queue_event_store_ready() -> None:
    status = get_workflow_pack_queue_event_store_runtime_status()
    if status.status is RuntimeReadinessStatus.READY:
        return
    raise WorkflowPackQueueEventStoreNotReadyError(
        f"Workflow-pack queue event store is not ready: {status.detail} [{status.status.value}]"
    )


def record_workflow_pack_queue_event(
    *,
    queue_item_id: str,
    event_type: WorkflowPackQueueEventType,
    workflow_pack_id: str,
    workflow_pack_version: str,
    state: WorkflowPackQueueState,
    message: str,
    policy_id: str | None = None,
    lane: WorkflowPackQueueLane | None = None,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    reason_code: str | None = None,
    source_queue_item_id: str | None = None,
    recovery_action_type: WorkflowPackQueueRecoveryActionType | None = None,
    recovery_attempt_number: int | None = None,
    requested_by: str | None = None,
    evidence_ref: str | None = None,
    idempotency_key: str | None = None,
    idempotency_request_fingerprint: str | None = None,
    artifact_refs: list[ArtifactDescriptor] | None = None,
) -> WorkflowPackQueueEventDescriptor:
    ensure_workflow_pack_queue_event_store_ready()
    descriptor = WorkflowPackQueueEventDescriptor(
        event_id=f"workflow-pack-queue-event-{uuid4().hex}",
        queue_item_id=queue_item_id,
        event_type=event_type,
        policy_id=policy_id,
        workflow_pack_id=workflow_pack_id,
        workflow_pack_version=workflow_pack_version,
        lane=lane,
        state=state,
        caller_app=caller_app,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        reason_code=reason_code,
        source_queue_item_id=source_queue_item_id,
        recovery_action_type=recovery_action_type,
        recovery_attempt_number=recovery_attempt_number,
        requested_by=requested_by,
        evidence_ref=evidence_ref,
        idempotency_key=idempotency_key,
        idempotency_request_fingerprint=idempotency_request_fingerprint,
        artifact_refs=[artifact.model_copy(deep=True) for artifact in artifact_refs or []],
        message=message,
        recorded_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    get_workflow_pack_queue_event_store().save_event(
        WorkflowPackQueueEventRecord(descriptor=descriptor)
    )
    return descriptor


def build_workflow_pack_queue_event_catalog(
    *,
    queue_item_id: str | None = None,
    workflow_pack_id: str | None = None,
    limit: int = 100,
) -> WorkflowPackQueueEventCatalogResponse:
    ensure_workflow_pack_queue_event_store_ready()
    records = get_workflow_pack_queue_event_store().list_events(
        queue_item_id=queue_item_id,
        workflow_pack_id=workflow_pack_id,
        limit=limit,
    )
    return WorkflowPackQueueEventCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        queue_event_source_mode=settings.workflow_pack_queue_event_store_mode,
        event_count=len(records),
        events=[record.descriptor for record in records],
        status_summary=[
            "Workflow-pack queue events provide durable source evidence for queue admission decisions, release posture, and recovery decisions.",
            "Queue events do not replace active queue status, run-ledger lifecycle state, review state, or task-flow checkpoints.",
        ],
    )


def build_workflow_pack_queue_event_detail(
    *,
    queue_item_id: str,
    limit: int = 100,
) -> WorkflowPackQueueEventDetailResponse:
    ensure_workflow_pack_queue_event_store_ready()
    records = get_workflow_pack_queue_event_store().list_events(
        queue_item_id=queue_item_id,
        limit=limit,
    )
    if not records:
        raise ValueError(f"Unknown workflow-pack queue item history: {queue_item_id}")
    events = [record.descriptor for record in records]
    events.sort(key=lambda event: (event.recorded_at, event.event_id))
    return WorkflowPackQueueEventDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        queue_event_source_mode=settings.workflow_pack_queue_event_store_mode,
        queue_item_id=queue_item_id,
        event_count=len(events),
        events=events,
        status_summary=[
            "Queue event detail is bounded to one queue item and ordered from request through terminal queue posture.",
            "Terminal queue posture and recovery decisions remain separate from workflow-pack run supportability, review authority, and actual replacement execution.",
        ],
    )
