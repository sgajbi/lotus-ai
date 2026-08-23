from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncJobArtifactDescriptor
from app.contracts.audit import AuditRecordResponse
from app.contracts.capability_packs import CapabilityPackObservabilitySummaryResponse
from app.services.async_job_service import build_async_job_catalog
from app.services.audit_store import get_audit_store
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.services.capability_pack_catalog import get_capability_pack_by_id
from app.services.runtime_readiness import get_audit_store_runtime_status


def build_capability_pack_observability_summary(
    *, pack_id: str
) -> CapabilityPackObservabilitySummaryResponse:
    _require_pack(pack_id=pack_id)
    records = [
        record
        for record in get_audit_store().list(
            scope=INTERNAL_AGGREGATE_AUDIT_SCOPE,
            limit=100,
        )
        if _matches_pack_record(record, pack_id)
    ]
    jobs = [job for job in build_async_job_catalog().jobs if _matches_pack_job(job, pack_id)]
    audit_store_ready = get_audit_store_runtime_status().status in {"READY", "DEGRADED"}
    observed_callers = sorted(
        {record.caller_app for record in records} | {job.caller_app for job in jobs}
    )
    incident_signal_count = sum(
        1
        for record in records
        if not record.authorization.allowed
        or record.safety_outcome.disposition.value != "DOCUMENTED_ONLY"
        or record.provider_mode not in {"disabled", "stub", "catalog_only"}
    )
    linked_endpoints = _build_linked_endpoints(pack_id=pack_id)
    observability_ready = audit_store_ready and len(linked_endpoints) > 0
    return CapabilityPackObservabilitySummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack_id=pack_id,
        observability_ready=observability_ready,
        sampled_audit_record_count=len(records),
        sampled_async_job_count=len(jobs),
        incident_signal_count=incident_signal_count,
        observed_caller_apps=observed_callers,
        linked_endpoints=linked_endpoints,
        status_summary=_build_status_summary(
            pack_id=pack_id,
            observability_ready=observability_ready,
            audit_record_count=len(records),
            async_job_count=len(jobs),
            incident_signal_count=incident_signal_count,
        ),
    )


def _matches_pack_record(record: AuditRecordResponse, pack_id: str) -> bool:
    if pack_id == "analytics_commentary.pack.v1":
        return record.task_id == "explain.v1" and record.caller_app == "lotus-performance"
    if pack_id == "decision_explanation.pack.v1":
        return record.task_id == "explain.v1" and record.caller_app == "lotus-manage"
    return False


def _matches_pack_job(job: AsyncJobArtifactDescriptor, pack_id: str) -> bool:
    if pack_id == "analytics_commentary.pack.v1":
        return job.caller_app == "lotus-performance"
    if pack_id == "decision_explanation.pack.v1":
        return job.caller_app == "lotus-manage"
    return False


def _build_linked_endpoints(*, pack_id: str) -> list[str]:
    endpoints = [
        f"/platform/capability-packs/{pack_id}",
        f"/platform/capability-packs/{pack_id}/governance-status",
        "/platform/observability/breakdowns",
        "/platform/evals/runtime-status",
    ]
    if pack_id == "analytics_commentary.pack.v1":
        endpoints.extend(
            [
                "/platform/use-cases/first-production-use-case",
                "/platform/use-cases/first-production-use-case/governance-status",
            ]
        )
    return endpoints


def _build_status_summary(
    *,
    pack_id: str,
    observability_ready: bool,
    audit_record_count: int,
    async_job_count: int,
    incident_signal_count: int,
) -> list[str]:
    family_label = (
        "analytics commentary"
        if pack_id == "analytics_commentary.pack.v1"
        else "decision explanation"
    )
    return [
        f"{family_label.capitalize()} pack observability reuses bounded audit and async job samples rather than introducing a separate product telemetry store.",
        (
            f"Recent bounded samples currently include {audit_record_count} audit record(s), {async_job_count} async job(s), and {incident_signal_count} incident signal(s)."
            if observability_ready
            else "Pack observability is blocked because the supporting audit surface is not currently reviewable."
        ),
    ]


def _require_pack(*, pack_id: str) -> None:
    if get_capability_pack_by_id(pack_id) is None:
        raise ValueError(f"Unknown capability pack: {pack_id}")
