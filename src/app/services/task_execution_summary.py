from __future__ import annotations

from collections import Counter

from app.config import settings
from app.contracts.task_runtime import (
    TaskExecutionCategorySample,
    TaskExecutionProviderSample,
    TaskExecutionSummaryResponse,
)
from app.services.audit_store import get_audit_store
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE


def build_task_execution_summary(*, limit: int = 100) -> TaskExecutionSummaryResponse:
    records = get_audit_store().list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=limit)
    category_counts = Counter(record.category for record in records)
    provider_mode_counts = Counter(record.provider_mode for record in records)
    latest_generated_at = records[0].generated_at if records else None
    return TaskExecutionSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        sampled_record_limit=limit,
        sampled_record_count=len(records),
        stubbed_execution_count=sum(1 for record in records if record.stubbed),
        non_stubbed_execution_count=sum(1 for record in records if not record.stubbed),
        latest_generated_at=latest_generated_at,
        categories=[
            TaskExecutionCategorySample(category=category, execution_count=count)
            for category, count in sorted(category_counts.items(), key=lambda item: item[0].value)
        ],
        provider_modes=[
            TaskExecutionProviderSample(provider_mode=provider_mode, execution_count=count)
            for provider_mode, count in sorted(provider_mode_counts.items())
        ],
    )
