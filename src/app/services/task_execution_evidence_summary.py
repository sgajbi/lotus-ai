from __future__ import annotations

from collections import Counter

from app.config import settings
from app.contracts.audit import AuditRecordResponse
from app.contracts.task_runtime import (
    TaskExecutionAnswerModeSample,
    TaskExecutionEvidenceSummaryResponse,
    TaskExecutionEvidenceTypeSample,
)
from app.services.audit_store import get_audit_store
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE


def build_task_execution_evidence_summary(
    *, limit: int = 100
) -> TaskExecutionEvidenceSummaryResponse:
    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=limit)
    answer_modes = [
        answer_mode
        for record in records
        for answer_mode in [_extract_answer_mode(record)]
        if answer_mode is not None
    ]
    answer_mode_counts = Counter(answer_modes)
    evidence_type_counts = Counter(
        descriptor.evidence_type for record in records for descriptor in record.evidence.descriptors
    )
    latest_generated_at = records[0].generated_at if records else None

    return TaskExecutionEvidenceSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        sampled_record_limit=limit,
        sampled_record_count=len(records),
        citation_bearing_execution_count=sum(
            1 for record in records if _has_structured_citations(record)
        ),
        citation_backed_answer_count=answer_mode_counts.get("CITATION_BACKED", 0),
        refused_answer_count=answer_mode_counts.get("REFUSED_INSUFFICIENT_SUPPORT", 0),
        latest_generated_at=latest_generated_at,
        answer_modes=[
            TaskExecutionAnswerModeSample(answer_mode=answer_mode, execution_count=count)
            for answer_mode, count in sorted(answer_mode_counts.items())
        ],
        evidence_types=[
            TaskExecutionEvidenceTypeSample(evidence_type=evidence_type, execution_count=count)
            for evidence_type, count in sorted(evidence_type_counts.items())
        ],
    )


def _extract_answer_mode(record: AuditRecordResponse) -> str | None:
    answer_mode = record.structured_output.get("answer_mode")
    return answer_mode if isinstance(answer_mode, str) else None


def _has_structured_citations(record: AuditRecordResponse) -> bool:
    citations = record.structured_output.get("citations")
    return isinstance(citations, list) and len(citations) > 0
