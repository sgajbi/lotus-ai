from __future__ import annotations

from collections import Counter

from app.config import settings
from app.contracts.audit import AuditRecordResponse
from app.contracts.task_runtime import (
    TaskExecutionAnswerModeSample,
    TaskRetrievalExecutionSourceSample,
    TaskRetrievalExecutionStatusSample,
    TaskRetrievalExecutionSummaryResponse,
    TaskRetrievalExecutionTaskSample,
)
from app.services.audit_store import get_audit_store

_RETRIEVAL_TASK_IDS = {"knowledge_search.v1", "knowledge_answer.v1"}


def build_task_retrieval_execution_summary(
    *, limit: int = 100
) -> TaskRetrievalExecutionSummaryResponse:
    records = [
        record for record in get_audit_store().list(limit=limit) if record.task_id in _RETRIEVAL_TASK_IDS
    ]
    task_counts = Counter(record.task_id for record in records)
    retrieval_status_counts = Counter(
        retrieval_status
        for record in records
        for retrieval_status in [_extract_retrieval_status(record)]
        if retrieval_status is not None
    )
    answer_mode_counts = Counter(
        answer_mode
        for record in records
        for answer_mode in [_extract_answer_mode(record)]
        if answer_mode is not None
    )
    source_counts = Counter(
        source_id
        for record in records
        for source_id in _extract_source_ids(record)
    )
    latest_generated_at = records[0].generated_at if records else None

    return TaskRetrievalExecutionSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        sampled_record_limit=limit,
        sampled_record_count=len(records),
        retrieval_execution_count=len(records),
        knowledge_search_execution_count=task_counts.get("knowledge_search.v1", 0),
        knowledge_answer_execution_count=task_counts.get("knowledge_answer.v1", 0),
        refused_answer_count=answer_mode_counts.get("REFUSED_INSUFFICIENT_SUPPORT", 0),
        latest_generated_at=latest_generated_at,
        tasks=[
            TaskRetrievalExecutionTaskSample(task_id=task_id, execution_count=count)
            for task_id, count in sorted(task_counts.items())
        ],
        retrieval_statuses=[
            TaskRetrievalExecutionStatusSample(retrieval_status=status, execution_count=count)
            for status, count in sorted(retrieval_status_counts.items())
        ],
        answer_modes=[
            TaskExecutionAnswerModeSample(answer_mode=answer_mode, execution_count=count)
            for answer_mode, count in sorted(answer_mode_counts.items())
        ],
        sources=[
            TaskRetrievalExecutionSourceSample(source_id=source_id, execution_count=count)
            for source_id, count in sorted(source_counts.items())
        ],
    )


def _extract_retrieval_status(record: AuditRecordResponse) -> str | None:
    retrieval_status = record.structured_output.get("retrieval_status")
    return retrieval_status if isinstance(retrieval_status, str) else None


def _extract_answer_mode(record: AuditRecordResponse) -> str | None:
    answer_mode = record.structured_output.get("answer_mode")
    return answer_mode if isinstance(answer_mode, str) else None


def _extract_source_ids(record: AuditRecordResponse) -> list[str]:
    source_ids = record.structured_output.get("source_ids")
    if not isinstance(source_ids, list):
        return []
    return [source_id for source_id in source_ids if isinstance(source_id, str)]
