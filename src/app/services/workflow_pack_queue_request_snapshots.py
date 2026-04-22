from __future__ import annotations

import hashlib
import json

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.tasks import TaskExecutionRequest
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueLane,
)
from app.contracts.workflow_packs import (
    WorkflowPackCallerIdentityClass,
    WorkflowPackEnvironment,
    WorkflowPackExecutionRequest,
    WorkflowPackRegistrationDescriptor,
)
from app.services.artifact_payloads import persist_or_reuse_json_artifact
from app.services.artifact_store import get_artifact_object_store

QUEUE_REQUEST_SNAPSHOT_ARTIFACT_TYPE = "queue_request_snapshot"


def persist_workflow_pack_queue_request_snapshot(
    *,
    queue_item_id: str,
    registration: WorkflowPackRegistrationDescriptor,
    lane: WorkflowPackQueueLane,
    task_request: TaskExecutionRequest,
    workflow_surface: str | None,
    environment: WorkflowPackEnvironment | None,
    caller_identity_class: WorkflowPackCallerIdentityClass | None,
    created_at: str,
) -> ArtifactDescriptor:
    payload = json.dumps(
        {
            "queue_item_id": queue_item_id,
            "pack_id": registration.pack_id,
            "pack_version": registration.version,
            "registration_ref": f"{registration.pack_id}@{registration.version}",
            "workflow_authority_owner": registration.workflow_authority_owner,
            "queue_lane": lane.value,
            "workflow_surface": workflow_surface,
            "environment": environment.value if environment is not None else None,
            "caller_identity_class": (
                caller_identity_class.value if caller_identity_class is not None else None
            ),
            "task_request": task_request.model_dump(mode="json"),
        },
        sort_keys=True,
    ).encode("utf-8")
    return persist_or_reuse_json_artifact(
        domain="workflow_pack",
        artifact_type=QUEUE_REQUEST_SNAPSHOT_ARTIFACT_TYPE,
        source_object_kind="workflow_pack_queue_item",
        source_object_id=queue_item_id,
        created_at=created_at,
        created_by="lotus-ai.workflow-pack-queue-admission",
        payload_json=payload,
        retention_posture="retained_for_recovery",
    )


def build_workflow_pack_execution_request_from_queue_snapshot(
    *,
    source_event: WorkflowPackQueueEventDescriptor,
) -> WorkflowPackExecutionRequest:
    snapshot_ref = _resolve_queue_request_snapshot_ref(source_event=source_event)
    payload = load_workflow_pack_queue_request_snapshot_payload(snapshot_ref=snapshot_ref)
    _validate_snapshot_payload(payload=payload, source_event=source_event)
    return WorkflowPackExecutionRequest.model_validate(
        {
            "pack_id": payload["pack_id"],
            "version": payload["pack_version"],
            "environment": payload["environment"],
            "caller_identity_class": payload["caller_identity_class"],
            "workflow_surface": payload.get("workflow_surface"),
            "queue_lane": payload.get("queue_lane"),
            "task_request": payload["task_request"],
        }
    )


def load_workflow_pack_queue_request_snapshot_payload(
    *,
    snapshot_ref: ArtifactDescriptor,
) -> dict[str, object]:
    object_key = _parse_storage_reference(snapshot_ref.storage_reference)
    snapshot_object = get_artifact_object_store().get_object(object_key=object_key)
    if snapshot_object is None:
        raise ValueError(
            "Workflow-pack queue recovery execution requires an available request snapshot object."
        )
    if hashlib.sha256(snapshot_object.payload).hexdigest() != snapshot_ref.checksum_sha256:
        raise ValueError(
            "Workflow-pack queue recovery execution request snapshot checksum does not match."
        )
    payload = json.loads(snapshot_object.payload)
    if not isinstance(payload, dict):
        raise ValueError("Workflow-pack queue request snapshot payload must be an object.")
    return payload


def _resolve_queue_request_snapshot_ref(
    *,
    source_event: WorkflowPackQueueEventDescriptor,
) -> ArtifactDescriptor:
    matches = [
        artifact
        for artifact in source_event.artifact_refs
        if artifact.domain == "workflow_pack"
        and artifact.artifact_type == QUEUE_REQUEST_SNAPSHOT_ARTIFACT_TYPE
        and artifact.source_object_kind == "workflow_pack_queue_item"
        and artifact.source_object_id == source_event.queue_item_id
    ]
    if not matches:
        raise ValueError(
            "Workflow-pack queue recovery execution requires a request snapshot artifact ref."
        )
    return matches[0]


def _validate_snapshot_payload(
    *,
    payload: object,
    source_event: WorkflowPackQueueEventDescriptor,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Workflow-pack queue request snapshot payload must be an object.")
    expected_values = {
        "queue_item_id": source_event.queue_item_id,
        "pack_id": source_event.workflow_pack_id,
        "pack_version": source_event.workflow_pack_version,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            raise ValueError(
                "Workflow-pack queue request snapshot does not match the source queue event."
            )
    if payload.get("environment") is None or payload.get("caller_identity_class") is None:
        raise ValueError(
            "Workflow-pack queue request snapshot does not include explicit execution context."
        )
    if "task_request" not in payload:
        raise ValueError("Workflow-pack queue request snapshot is missing task_request.")


def _parse_storage_reference(storage_reference: str) -> str:
    _, _, object_key = storage_reference.partition("://")
    return object_key
