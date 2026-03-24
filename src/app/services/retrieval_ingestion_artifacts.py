from __future__ import annotations

import json

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.retrieval import RetrievalIngestionJobDescriptor
from app.services.artifact_payloads import persist_or_reuse_json_artifact
from app.services.artifact_store import get_artifact_repository


def persist_retrieval_ingestion_diagnostic_artifact(
    *,
    job: RetrievalIngestionJobDescriptor,
    created_at: str,
    created_by: str,
    runtime_async_job_id: str | None,
    follow_on_async_job_id: str | None,
) -> ArtifactDescriptor:
    payload = json.dumps(
        {
            "job_id": job.job_id,
            "source_id": job.source_id,
            "document_id": job.document_id,
            "target_version_id": job.target_version_id,
            "requested_action": job.requested_action.value,
            "status": job.status.value,
            "requested_by": job.requested_by,
            "requested_at": job.requested_at,
            "runtime_status": job.runtime_status,
            "linked_async_job_id": runtime_async_job_id,
            "follow_on_async_job_id": follow_on_async_job_id,
            "message": job.message,
        },
        sort_keys=True,
    ).encode("utf-8")
    return persist_or_reuse_json_artifact(
        domain="retrieval",
        artifact_type="ingestion_diagnostic",
        source_object_kind="retrieval_ingestion_job",
        source_object_id=job.job_id,
        created_at=created_at,
        created_by=created_by,
        payload_json=payload,
        retention_posture="retained_for_review",
    )


def load_retrieval_ingestion_artifact_refs(*, job_id: str) -> list[ArtifactDescriptor]:
    artifacts = [
        ArtifactDescriptor.model_validate(record.__dict__)
        for record in get_artifact_repository().list_artifacts()
        if record.domain == "retrieval"
        and record.artifact_type == "ingestion_diagnostic"
        and record.source_object_kind == "retrieval_ingestion_job"
        and record.source_object_id == job_id
    ]
    artifacts.sort(key=lambda item: item.created_at, reverse=True)
    return artifacts[:3]
