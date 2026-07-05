from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSourceEventResponse,
    WorkflowPackRunSupportabilityStatus,
    WorkflowPackSourceEventCatalogResponse,
    WorkflowPackSourceEventDescriptor,
    WorkflowPackSourceEventType,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)
from app.services.artifact_object_store import StoredArtifactObject
from app.services.artifact_store import get_artifact_object_store
from app.services.workflow_pack_run_ledger import (
    ensure_workflow_pack_run_store_ready,
    load_workflow_pack_run_context,
    map_workflow_pack_run_record,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_run_supportability import (
    resolve_workflow_pack_run_record_supportability_status,
)

SOURCE_EVENT_RETENTION_POLICY = "AI_WORKFLOW_PACK_SOURCE_EVENT_7Y"
SOURCE_EVENT_REDACTION_POLICY = "NO_RAW_PAYLOADS"
SOURCE_EVENT_AUDIT_POLICY = "AUDIT_READ_AND_EXPORT"
SOURCE_EVENT_ACCESS_CLASSIFICATION = "CLIENT_CONFIDENTIAL_INTERNAL"
SOURCE_AUTHORITY_POLICY = (
    "lotus-ai source events describe AI workflow-pack execution and review lineage only; "
    "consumers must not reconstruct portfolio-memory, risk, performance, execution, tax, cash, "
    "FX, report, or client-communication facts from this projection."
)
CONTENT_HASH_UNAVAILABLE = "content_hash_unavailable"
SOURCE_EVENT_RUN_QUERY_WINDOW_MULTIPLIER = 10
SOURCE_EVENT_RUN_QUERY_WINDOW_MAX = 500


def build_workflow_pack_source_event_catalog(
    *,
    pack_id: str | None = None,
    caller_app: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None = None,
    limit: int = 100,
) -> WorkflowPackSourceEventCatalogResponse:
    ensure_workflow_pack_run_store_ready()
    store = get_workflow_pack_run_store()
    source_run_limit = _source_run_query_limit(
        limit=limit, supportability_status=supportability_status
    )
    runs = store.query_runs(
        pack_id=pack_id,
        caller_app=caller_app,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        limit=source_run_limit,
    )
    filtered_runs = [
        record
        for record in runs
        if _run_matches_filters(
            record=record,
            supportability_status=supportability_status,
        )
    ]
    events = [
        source_event
        for run in filtered_runs
        for source_event in _build_source_events_for_run(
            record=run,
            ledger_events=store.list_events(run_id=run.run_id),
        )
    ]
    events.sort(key=lambda item: item.recorded_at, reverse=True)
    limited_events = events[:limit]
    filters_applied: dict[str, str | int] = {"limit": limit}
    filters_applied["source_run_limit"] = source_run_limit
    filters_applied["source_run_count"] = len(runs)
    if pack_id is not None:
        filters_applied["pack_id"] = pack_id
    if caller_app is not None:
        filters_applied["caller_app"] = caller_app
    if tenant_id is not None:
        filters_applied["tenant_id"] = tenant_id
    if workflow_surface is not None:
        filters_applied["workflow_surface"] = workflow_surface
    if supportability_status is not None:
        filters_applied["supportability_status"] = supportability_status.value

    return WorkflowPackSourceEventCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        event_count=len(limited_events),
        filters_applied=filters_applied,
        ready_count=_count_by_status(limited_events, WorkflowPackRunSupportabilityStatus.READY),
        action_required_count=_count_by_status(
            limited_events,
            WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        ),
        historical_count=_count_by_status(
            limited_events,
            WorkflowPackRunSupportabilityStatus.HISTORICAL,
        ),
        no_raw_payloads=True,
        source_authority_policy=SOURCE_AUTHORITY_POLICY,
        events=limited_events,
        notes=_source_event_notes(),
    )


def build_workflow_pack_run_source_events(*, run_id: str) -> WorkflowPackRunSourceEventResponse:
    loaded = load_workflow_pack_run_context(run_id=run_id)
    events = _build_source_events_for_run(record=loaded.record, ledger_events=loaded.events)
    return WorkflowPackRunSourceEventResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        run_id=run_id,
        event_count=len(events),
        no_raw_payloads=True,
        source_authority_policy=SOURCE_AUTHORITY_POLICY,
        events=events,
        notes=_source_event_notes(),
    )


def _build_source_events_for_run(
    *,
    record: WorkflowPackRunRecord,
    ledger_events: list[WorkflowPackRunEventRecord],
) -> list[WorkflowPackSourceEventDescriptor]:
    run_descriptor = map_workflow_pack_run_record(record)
    artifact_payload = _load_run_output_summary(record.artifact_refs)
    content_hash = _content_hash(record.artifact_refs)
    source_refs = _source_refs(artifact_payload)
    portfolio_id = _string_from_structured_output(artifact_payload, "portfolio_id")
    portfolio_memory_status = _string_from_structured_output(
        artifact_payload,
        "portfolio_memory_status",
    )
    portfolio_memory_content_hash = _string_from_structured_output(
        artifact_payload,
        "portfolio_memory_content_hash",
    )
    event_ref_count = _int_from_structured_output(
        artifact_payload,
        "portfolio_memory_event_ref_count",
    )

    return [
        WorkflowPackSourceEventDescriptor(
            event_identity=_source_event_identity(
                source_type=_source_type(event),
                source_id=f"{record.run_id}:{event.event_id}",
                content_hash=content_hash,
            ),
            event_type=_source_event_type(event),
            source_system="lotus-ai",
            source_type=_source_type(event),
            source_id=f"{record.run_id}:{event.event_id}",
            content_hash=content_hash,
            portfolio_id=portfolio_id,
            run_id=record.run_id,
            pack_id=record.pack_id,
            pack_version=record.pack_version,
            caller_app=record.caller_app,
            tenant_id=record.tenant_id,
            workflow_surface=record.workflow_surface,
            workflow_authority_owner=record.workflow_authority_owner,
            runtime_state=WorkflowPackRunRuntimeState(record.runtime_state),
            review_state=WorkflowPackRunReviewState(record.review_state),
            supportability_status=run_descriptor.supportability_status,
            portfolio_memory_status=portfolio_memory_status,
            portfolio_memory_content_hash=portfolio_memory_content_hash,
            event_ref_count=event_ref_count,
            retention_policy=SOURCE_EVENT_RETENTION_POLICY,
            redaction_policy=SOURCE_EVENT_REDACTION_POLICY,
            audit_policy=SOURCE_EVENT_AUDIT_POLICY,
            access_classification=SOURCE_EVENT_ACCESS_CLASSIFICATION,
            source_refs=source_refs,
            artifact_refs=[artifact.model_copy(deep=True) for artifact in record.artifact_refs],
            evidence_descriptor_count=len(record.evidence_descriptors),
            recovery_lineage=run_descriptor.recovery_lineage,
            recorded_at=event.recorded_at,
        )
        for event in ledger_events
    ]


def _run_matches_filters(
    *,
    record: WorkflowPackRunRecord,
    supportability_status: WorkflowPackRunSupportabilityStatus | None,
) -> bool:
    if supportability_status is not None:
        resolved = resolve_workflow_pack_run_record_supportability_status(record)
        if resolved is not supportability_status:
            return False
    return True


def _source_run_query_limit(
    *,
    limit: int,
    supportability_status: WorkflowPackRunSupportabilityStatus | None,
) -> int:
    bounded_limit = max(limit, 0)
    if supportability_status is None:
        return bounded_limit
    return min(
        max(bounded_limit * SOURCE_EVENT_RUN_QUERY_WINDOW_MULTIPLIER, bounded_limit),
        SOURCE_EVENT_RUN_QUERY_WINDOW_MAX,
    )


def _load_run_output_summary(artifact_refs: list[ArtifactDescriptor]) -> dict[str, Any]:
    summary_artifact = next(
        (
            artifact
            for artifact in artifact_refs
            if artifact.domain == "workflow_pack"
            and artifact.artifact_type == "run_output_summary"
            and artifact.storage_reference
        ),
        None,
    )
    if summary_artifact is None:
        return {}
    _, _, object_key = summary_artifact.storage_reference.partition("://")
    stored_object: StoredArtifactObject | None = get_artifact_object_store().get_object(
        object_key=object_key
    )
    if stored_object is None:
        return {}
    try:
        payload = json.loads(stored_object.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_refs(artifact_payload: dict[str, Any]) -> list[str]:
    source_refs = artifact_payload.get("source_refs")
    if not isinstance(source_refs, list):
        return []
    return sorted(item for item in source_refs if isinstance(item, str))


def _string_from_structured_output(artifact_payload: dict[str, Any], key: str) -> str:
    structured_output = artifact_payload.get("structured_output")
    if not isinstance(structured_output, dict):
        return ""
    value = structured_output.get(key)
    return value if isinstance(value, str) else ""


def _int_from_structured_output(artifact_payload: dict[str, Any], key: str) -> int:
    structured_output = artifact_payload.get("structured_output")
    if not isinstance(structured_output, dict):
        return 0
    value = structured_output.get(key)
    return value if isinstance(value, int) else 0


def _content_hash(artifact_refs: list[ArtifactDescriptor]) -> str:
    artifact = next((item for item in artifact_refs if item.checksum_sha256), None)
    if artifact is None:
        return CONTENT_HASH_UNAVAILABLE
    return f"sha256:{artifact.checksum_sha256}"


def _source_event_identity(*, source_type: str, source_id: str, content_hash: str) -> str:
    return f"lotus-ai:{source_type}:{source_id}:{content_hash}"


def _source_type(event: WorkflowPackRunEventRecord) -> str:
    return {
        "RUN_RECORDED": "AI_WORKFLOW_PACK_RUN",
        "REVIEW_STATE_UPDATED": "AI_WORKFLOW_PACK_REVIEW",
        "LINEAGE_UPDATED": "AI_WORKFLOW_PACK_LINEAGE",
    }.get(event.event_type, "AI_WORKFLOW_PACK_RUN")


def _source_event_type(event: WorkflowPackRunEventRecord) -> WorkflowPackSourceEventType:
    return {
        "RUN_RECORDED": WorkflowPackSourceEventType.AI_WORKFLOW_PACK_RUN_RECORDED,
        "REVIEW_STATE_UPDATED": WorkflowPackSourceEventType.AI_WORKFLOW_PACK_REVIEW_STATE_UPDATED,
        "LINEAGE_UPDATED": WorkflowPackSourceEventType.AI_WORKFLOW_PACK_LINEAGE_UPDATED,
    }.get(event.event_type, WorkflowPackSourceEventType.AI_WORKFLOW_PACK_RUN_RECORDED)


def _count_by_status(
    events: list[WorkflowPackSourceEventDescriptor],
    status: WorkflowPackRunSupportabilityStatus,
) -> int:
    return sum(1 for event in events if event.supportability_status is status)


def _source_event_notes() -> list[str]:
    return [
        "Source events are projected from lotus-ai workflow-pack run-ledger truth; they are not a second event store.",
        "The projection emits AI execution, review, and lineage events only and preserves downstream workflow authority ownership.",
        "Raw prompts, raw generated output, and raw portfolio-memory payloads are deliberately omitted.",
        "Portfolio-memory fields are limited to bounded lineage counts, status, and content hash when supplied.",
    ]
