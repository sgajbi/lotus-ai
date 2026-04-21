from __future__ import annotations

import json

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.tasks import TaskExecutionResponse
from app.services.artifact_payloads import persist_or_reuse_json_artifact
from app.services.task_execution_models import TaskExecutionContext


def persist_workflow_pack_run_output_artifact(
    *,
    run_id: str,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
    pack_id: str,
    pack_version: str,
    review_required: bool,
    review_state: str,
    created_at: str,
) -> ArtifactDescriptor:
    payload = json.dumps(
        {
            "run_id": run_id,
            "pack_id": pack_id,
            "pack_version": pack_version,
            "task_id": response.task_id,
            "request_id": context.request_id,
            "caller_app": context.request.caller.caller_app,
            "correlation_id": context.request.caller.correlation_id,
            "tenant_id": context.request.caller.tenant_id,
            "review_required": review_required,
            "review_state": review_state,
            "provider_mode": response.audit.provider_mode,
            "stubbed": response.audit.stubbed,
            "source_refs": list(context.request.context.source_refs),
            "output_preview": response.result.message,
            "structured_output": response.result.structured_output,
            "evidence_types": [
                descriptor.evidence_type for descriptor in response.evidence.descriptors
            ],
        },
        sort_keys=True,
    ).encode("utf-8")
    return persist_or_reuse_json_artifact(
        domain="workflow_pack",
        artifact_type="run_output_summary",
        source_object_kind="workflow_pack_run",
        source_object_id=run_id,
        created_at=created_at,
        created_by="lotus-ai.workflow-pack-run-ledger",
        payload_json=payload,
        retention_posture="retained_for_review",
    )
