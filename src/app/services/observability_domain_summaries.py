from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.observability import (
    DomainIncidentSummaryResponse,
    ObservabilityBreakdownSupport,
    ObservabilityDomainId,
)
from app.services.async_runtime_status import build_async_runtime_status
from app.services.observability_shared import (
    build_domain_telemetry_summary,
    build_incident_evidence_item,
)
from app.services.provider_operations_status import build_provider_operations_status
from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.runtime_readiness import get_retrieval_store_runtime_status


@dataclass(frozen=True)
class ObservabilityDomainBundle:
    summary: DomainIncidentSummaryResponse


def build_provider_observability_bundle() -> ObservabilityDomainBundle:
    provider_operations = build_provider_operations_status()
    degraded_findings = list(provider_operations.blocking_reasons)
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.PROVIDER,
        telemetry_sources=[
            "provider_operations_status",
            "correlation_middleware",
            "prometheus",
        ],
        source_available=True,
        degraded_findings=degraded_findings,
        stale=False,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=True,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            f"Provider operations currently report `{provider_operations.operations_state.value}` posture.",
            "Provider incident summaries are grounded in runtime provider operations state rather than runbook-only prose.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.PROVIDER,
            evidence_id="provider_operations_incident_state",
            source_available=True,
            stale=False,
            degraded_findings=degraded_findings,
            durable=settings.provider_operations_store_mode == "sqlalchemy",
            summary=(
                "Provider operations state captures rollout, quota, budget, and degradation findings for current incident review."
            ),
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.PROVIDER,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/providers/operations-status",
                "/platform/providers/governance-status",
                "/platform/providers/runbook-readiness",
            ],
            summary=[
                provider_operations.summary[0],
                (
                    provider_operations.blocking_reasons[0]
                    if provider_operations.blocking_reasons
                    else "No current provider blocking reason is active."
                ),
            ],
        )
    )


def build_retrieval_observability_bundle() -> ObservabilityDomainBundle:
    retrieval_execution = build_retrieval_execution_status()
    activation_readiness = build_retrieval_activation_readiness()
    store_status = get_retrieval_store_runtime_status()
    degraded_findings = list(activation_readiness.blocking_findings)
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.RETRIEVAL,
        telemetry_sources=[
            "retrieval_execution_status",
            "retrieval_activation_readiness",
            "correlation_middleware",
            "prometheus",
        ],
        source_available=store_status.status == "READY" or settings.retrieval_store_mode == "memory",
        degraded_findings=degraded_findings,
        stale=False,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=True,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            retrieval_execution.message,
            "Retrieval incident summaries are grounded in searchable-corpus, evidence, and activation state.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.RETRIEVAL,
            evidence_id="retrieval_live_search_activation_state",
            source_available=store_status.status == "READY" or settings.retrieval_store_mode == "memory",
            stale=False,
            degraded_findings=degraded_findings,
            durable=settings.retrieval_store_mode == "sqlalchemy" and store_status.status == "READY",
            summary="Retrieval activation state captures searchable corpus, reindex, rollback, and evidence blockers for current incident review.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.RETRIEVAL,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/retrieval/execution-status",
                "/platform/retrieval/activation-readiness",
                "/platform/retrieval/governance-status",
            ],
            summary=[
                retrieval_execution.message,
                (
                    activation_readiness.blocking_findings[0]
                    if activation_readiness.blocking_findings
                    else "Retrieval activation currently has no incident blocker."
                ),
            ],
        )
    )


def build_async_observability_bundle() -> ObservabilityDomainBundle:
    async_runtime = build_async_runtime_status()
    degraded_findings = list(async_runtime.degraded_findings)
    telemetry = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.ASYNC,
        telemetry_sources=["async_runtime_status", "async_delivery_queue", "prometheus"],
        source_available=True,
        degraded_findings=degraded_findings,
        stale=False,
        incident_evidence_supported=True,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=False,
            capability_supported=True,
        ),
        incident_signal_count=len(degraded_findings),
        summary=[
            async_runtime.message,
            "Async incident summaries are grounded in queue backlog, worker identity, and degraded-fallback state.",
        ],
    )
    incident_items = [
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.ASYNC,
            evidence_id="async_worker_fleet_state",
            source_available=True,
            stale=False,
            degraded_findings=degraded_findings,
            durable=settings.async_runtime_store_mode == "sqlalchemy",
            summary="Async worker-fleet state captures queue backlog, worker visibility, drain mode, and explicit degraded fallback.",
        )
    ]
    return ObservabilityDomainBundle(
        summary=DomainIncidentSummaryResponse(
            service=settings.service_name,
            version=settings.service_version,
            domain_id=ObservabilityDomainId.ASYNC,
            telemetry=telemetry,
            incident_evidence_items=incident_items,
            linked_endpoints=[
                "/platform/async/runtime-status",
                "/platform/async/activation-readiness",
                "/platform/async/governance-status",
            ],
            summary=[
                async_runtime.message,
                (
                    async_runtime.degraded_findings[0]
                    if async_runtime.degraded_findings
                    else "Async runtime currently exposes no active degraded finding."
                ),
            ],
        )
    )


def build_slice_two_observability_bundles() -> list[ObservabilityDomainBundle]:
    return [
        build_provider_observability_bundle(),
        build_retrieval_observability_bundle(),
        build_async_observability_bundle(),
    ]
