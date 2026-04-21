from __future__ import annotations

import json

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.tasks import TaskExecutionRequest
from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueLane
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.artifact_payloads import persist_or_reuse_json_artifact


def persist_workflow_pack_queue_request_snapshot(
    *,
    queue_item_id: str,
    registration: WorkflowPackRegistrationDescriptor,
    lane: WorkflowPackQueueLane,
    task_request: TaskExecutionRequest,
    workflow_surface: str | None,
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
            "task_request": task_request.model_dump(mode="json"),
        },
        sort_keys=True,
    ).encode("utf-8")
    return persist_or_reuse_json_artifact(
        domain="workflow_pack",
        artifact_type="queue_request_snapshot",
        source_object_kind="workflow_pack_queue_item",
        source_object_id=queue_item_id,
        created_at=created_at,
        created_by="lotus-ai.workflow-pack-queue-admission",
        payload_json=payload,
        retention_posture="retained_for_recovery",
    )
