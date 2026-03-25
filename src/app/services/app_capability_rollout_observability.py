from __future__ import annotations

from app.config import settings
from app.contracts.app_capability_rollouts import (
    AppCapabilityEstateVisibilityState,
    AppCapabilityRolloutObservabilityItem,
    AppCapabilityRolloutObservabilitySummaryResponse,
    AppCapabilityRolloutStage,
)
from app.contracts.audit import AuditRecordResponse
from app.contracts.async_runtime import AsyncJobArtifactDescriptor
from app.services.app_capability_rollout_catalog import (
    build_app_capability_rollout_catalog,
    build_app_capability_rollout_governance_status,
)
from app.services.async_job_service import build_async_job_catalog
from app.services.audit_store import get_audit_store
from app.services.runtime_readiness import get_audit_store_runtime_status


def build_app_capability_rollout_observability_summary(
    app_state: object | None = None,
) -> AppCapabilityRolloutObservabilitySummaryResponse:
    catalog = build_app_capability_rollout_catalog(app_state)
    audit_store_ready = get_audit_store_runtime_status().status in {"READY", "DEGRADED"}
    items = [
        _build_observability_item(
            downstream_app=record.downstream_app,
            capability_pack_id=record.capability_pack_id,
            app_state=app_state,
        )
        for record in catalog.rollout_records
    ]
    active_pairing_count = sum(
        1
        for item in items
        if item.estate_visibility_state is AppCapabilityEstateVisibilityState.ACTIVE
    )
    paused_pairing_count = sum(
        1
        for item in items
        if item.estate_visibility_state is AppCapabilityEstateVisibilityState.PAUSED
    )
    retired_pairing_count = sum(
        1
        for item in items
        if item.estate_visibility_state is AppCapabilityEstateVisibilityState.RETIRED
    )
    blocked_pairing_count = sum(
        1
        for item in items
        if item.estate_visibility_state is AppCapabilityEstateVisibilityState.BLOCKED
    )
    observed_pairing_count = sum(
        1
        for item in items
        if item.sampled_audit_record_count > 0 or item.sampled_async_job_count > 0
    )
    observability_ready = audit_store_ready and all(item.linked_endpoints for item in items)
    return AppCapabilityRolloutObservabilitySummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        observability_ready=observability_ready,
        pairing_count=len(items),
        active_pairing_count=active_pairing_count,
        blocked_pairing_count=blocked_pairing_count,
        paused_pairing_count=paused_pairing_count,
        retired_pairing_count=retired_pairing_count,
        observed_pairing_count=observed_pairing_count,
        items=items,
        status_summary=[
            "App-capability rollout observability now summarizes estate-wide pairing posture from the same rollout records and governance seams instead of introducing a parallel adoption registry.",
            (
                f"Current bounded rollout visibility covers {len(items)} pairing(s): {active_pairing_count} active, {blocked_pairing_count} blocked, {paused_pairing_count} paused, and {retired_pairing_count} retired."
                if observability_ready
                else "Estate-wide rollout visibility is blocked because the supporting audit-backed review surface is not currently ready."
            ),
        ],
    )


def _build_observability_item(
    *, downstream_app: str, capability_pack_id: str, app_state: object | None = None
) -> AppCapabilityRolloutObservabilityItem:
    governance = build_app_capability_rollout_governance_status(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
    )
    audit_records = [
        record
        for record in get_audit_store().list(limit=100)
        if _matches_pairing_record(
            record=record, downstream_app=downstream_app, capability_pack_id=capability_pack_id
        )
    ]
    async_jobs = [
        job
        for job in build_async_job_catalog().jobs
        if _matches_pairing_job(
            job=job, downstream_app=downstream_app, capability_pack_id=capability_pack_id
        )
    ]
    incident_signal_count = sum(
        1
        for record in audit_records
        if not record.authorization.allowed
        or record.safety_outcome.disposition.value != "DOCUMENTED_ONLY"
        or record.provider_mode not in {"disabled", "stub", "catalog_only"}
    )
    return AppCapabilityRolloutObservabilityItem(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        rollout_stage=governance.record.rollout_stage,
        estate_visibility_state=_resolve_estate_visibility_state(
            rollout_stage=governance.record.rollout_stage,
            governance_ready=governance.governance_ready,
        ),
        governance_ready=governance.governance_ready,
        sampled_audit_record_count=len(audit_records),
        sampled_async_job_count=len(async_jobs),
        incident_signal_count=incident_signal_count,
        linked_endpoints=_build_linked_endpoints(
            downstream_app=downstream_app, capability_pack_id=capability_pack_id
        ),
    )


def _resolve_estate_visibility_state(
    *, rollout_stage: AppCapabilityRolloutStage, governance_ready: bool
) -> AppCapabilityEstateVisibilityState:
    if rollout_stage is AppCapabilityRolloutStage.RETIRED:
        return AppCapabilityEstateVisibilityState.RETIRED
    if rollout_stage is AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK:
        return AppCapabilityEstateVisibilityState.PAUSED
    if (
        rollout_stage
        in {
            AppCapabilityRolloutStage.LIMITED_ROLLOUT,
            AppCapabilityRolloutStage.ACTIVE_PRODUCTION,
        }
        and governance_ready
    ):
        return AppCapabilityEstateVisibilityState.ACTIVE
    return AppCapabilityEstateVisibilityState.BLOCKED


def _matches_pairing_record(
    *,
    record: AuditRecordResponse,
    downstream_app: str,
    capability_pack_id: str,
) -> bool:
    if record.caller_app != downstream_app:
        return False
    if capability_pack_id == "analytics_commentary.pack.v1":
        return record.task_id == "explain.v1"
    if capability_pack_id == "decision_explanation.pack.v1":
        return record.task_id == "explain.v1"
    return False


def _matches_pairing_job(
    *,
    job: AsyncJobArtifactDescriptor,
    downstream_app: str,
    capability_pack_id: str,
) -> bool:
    if job.caller_app != downstream_app:
        return False
    if capability_pack_id == "analytics_commentary.pack.v1":
        return job.job_type in {"task_execution", "evaluation_run"}
    if capability_pack_id == "decision_explanation.pack.v1":
        return job.job_type in {"task_execution", "evaluation_run"}
    return False


def _build_linked_endpoints(*, downstream_app: str, capability_pack_id: str) -> list[str]:
    return [
        "/platform/app-capability-rollouts/observability-summary",
        f"/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}",
        f"/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}/governance-status",
        f"/platform/app-capability-rollouts/{downstream_app}/{capability_pack_id}/onboarding-template",
        "/platform/observability/incident-summary",
        "/platform/observability/breakdowns",
    ]
