from __future__ import annotations

from collections import Counter, defaultdict

from app.config import settings
from app.contracts.async_runtime import AsyncJobArtifactDescriptor
from app.contracts.audit import AuditRecordResponse
from app.contracts.observability import (
    ObservabilityBreakdownSummaryResponse,
    ObservabilityCallerBreakdownSample,
    ObservabilityCapabilityBreakdownSample,
    ObservabilityCapabilityKind,
    ObservabilityModelBreakdownSample,
    ObservabilityTenantBreakdownSample,
)
from app.contracts.audit_access import AuditReadScope
from app.services.async_job_service import build_async_job_catalog
from app.services.audit_store import get_audit_store

_RETRIEVAL_TASK_IDS = {"knowledge_search.v1", "knowledge_answer.v1"}
_NON_LIVE_PROVIDER_MODES = {"disabled", "stub", "catalog_only"}


def build_observability_breakdown_summary(
    *, limit: int = 100, scope: AuditReadScope
) -> ObservabilityBreakdownSummaryResponse:
    # The scope is the caller's, resolved from caller policy at the router -
    # never an implicit all-tenant read (issues #168/#159).
    records = get_audit_store().list(scope=scope, limit=limit)
    jobs = build_async_job_catalog().jobs
    return ObservabilityBreakdownSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        sampled_audit_record_limit=limit,
        sampled_audit_record_count=len(records),
        sampled_async_job_count=len(jobs),
        tenant_scope=scope.mode.value,
        tenant_breakdown_policy=(
            "Tenant breakdown is derived from the caller's authorized audit-read scope and "
            "includes only executions carrying tenant identity."
        ),
        caller_apps=_build_caller_samples(records=records, jobs=jobs),
        tenants=_build_tenant_samples(records=records),
        models=_build_model_samples(records=records),
        capabilities=_build_capability_samples(records=records, jobs=jobs),
        status_summary=[
            "Breakdown summary uses bounded recent audit records plus current async job catalog.",
            "Tenant visibility is restricted to authorized executions that already carry tenant identity.",
        ],
    )


def _build_caller_samples(
    *, records: list[AuditRecordResponse], jobs: list[AsyncJobArtifactDescriptor]
) -> list[ObservabilityCallerBreakdownSample]:
    callers = sorted({record.caller_app for record in records} | {job.caller_app for job in jobs})
    samples: list[ObservabilityCallerBreakdownSample] = []
    for caller_app in callers:
        caller_records = [record for record in records if record.caller_app == caller_app]
        caller_jobs = [job for job in jobs if job.caller_app == caller_app]
        samples.append(
            ObservabilityCallerBreakdownSample(
                caller_app=caller_app,
                execution_count=len(caller_records),
                allowed_execution_count=sum(
                    1 for record in caller_records if record.authorization.allowed
                ),
                retrieval_execution_count=sum(
                    1 for record in caller_records if record.task_id in _RETRIEVAL_TASK_IDS
                ),
                live_provider_execution_count=sum(
                    1
                    for record in caller_records
                    if record.provider_mode not in _NON_LIVE_PROVIDER_MODES
                ),
                async_job_count=len(caller_jobs),
            )
        )
    samples.sort(
        key=lambda sample: (-sample.execution_count, -sample.async_job_count, sample.caller_app)
    )
    return samples


def _build_tenant_samples(
    *, records: list[AuditRecordResponse]
) -> list[ObservabilityTenantBreakdownSample]:
    tenant_records = [
        record
        for record in records
        if record.authorization.allowed and record.tenant_id is not None
    ]
    grouped: dict[str, list[AuditRecordResponse]] = defaultdict(list)
    for record in tenant_records:
        grouped[record.tenant_id or ""].append(record)
    samples = [
        ObservabilityTenantBreakdownSample(
            tenant_id=tenant_id,
            execution_count=len(items),
            priced_execution_count=sum(1 for item in items if item.estimated_cost_usd is not None),
            estimated_cost_usd_total=round(
                sum(item.estimated_cost_usd or 0.0 for item in items), 8
            ),
            caller_app_count=len({item.caller_app for item in items}),
            capability_count=len({item.task_id for item in items}),
        )
        for tenant_id, items in grouped.items()
    ]
    samples.sort(key=lambda sample: (-sample.execution_count, sample.tenant_id))
    return samples


def _build_model_samples(
    *, records: list[AuditRecordResponse]
) -> list[ObservabilityModelBreakdownSample]:
    grouped: dict[str, list[AuditRecordResponse]] = defaultdict(list)
    for record in records:
        grouped[record.model_id or "unknown"].append(record)
    samples = [
        ObservabilityModelBreakdownSample(
            model_id=model_id,
            execution_count=len(items),
            priced_execution_count=sum(1 for item in items if item.estimated_cost_usd is not None),
            estimated_cost_usd_total=round(
                sum(item.estimated_cost_usd or 0.0 for item in items), 8
            ),
        )
        for model_id, items in grouped.items()
    ]
    samples.sort(
        key=lambda sample: (
            -sample.estimated_cost_usd_total,
            -sample.execution_count,
            sample.model_id,
        )
    )
    return samples


def _build_capability_samples(
    *, records: list[AuditRecordResponse], jobs: list[AsyncJobArtifactDescriptor]
) -> list[ObservabilityCapabilityBreakdownSample]:
    task_counts = Counter(record.task_id for record in records)
    retrieval_source_counts = Counter(
        source_id for record in records for source_id in _extract_source_ids(record)
    )
    async_job_type_counts = Counter(job.job_type for job in jobs)
    task_costs: dict[str, list[float | None]] = defaultdict(list)
    for record in records:
        task_costs[record.task_id].append(record.estimated_cost_usd)
    samples = [
        ObservabilityCapabilityBreakdownSample(
            capability_kind=ObservabilityCapabilityKind.TASK,
            capability_id=task_id,
            observed_count=count,
            priced_execution_count=sum(1 for cost in task_costs[task_id] if cost is not None),
            estimated_cost_usd_total=round(sum(cost or 0.0 for cost in task_costs[task_id]), 8),
        )
        for task_id, count in sorted(task_counts.items())
    ]
    samples.extend(
        ObservabilityCapabilityBreakdownSample(
            capability_kind=ObservabilityCapabilityKind.RETRIEVAL_SOURCE,
            capability_id=source_id,
            observed_count=count,
        )
        for source_id, count in sorted(retrieval_source_counts.items())
    )
    samples.extend(
        ObservabilityCapabilityBreakdownSample(
            capability_kind=ObservabilityCapabilityKind.ASYNC_JOB_TYPE,
            capability_id=job_type,
            observed_count=count,
        )
        for job_type, count in sorted(async_job_type_counts.items())
    )
    samples.sort(
        key=lambda sample: (
            -sample.observed_count,
            sample.capability_kind.value,
            sample.capability_id,
        )
    )
    return samples


def _extract_source_ids(record: AuditRecordResponse) -> list[str]:
    source_ids = record.structured_output.get("source_ids")
    if not isinstance(source_ids, list):
        return []
    return [source_id for source_id in source_ids if isinstance(source_id, str)]
