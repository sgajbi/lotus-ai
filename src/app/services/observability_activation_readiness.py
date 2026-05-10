from __future__ import annotations

from app.config import settings
from app.contracts.observability import (
    ObservabilityActivationReadinessResponse,
    ObservabilityRuntimeStatusResponse,
)
from app.services.access_control_runtime import build_access_control_runtime_status
from app.services.observability_runtime import build_observability_runtime_status
from app.services.runtime_readiness import get_audit_store_runtime_status


def build_observability_activation_readiness(
    *, runtime_status: ObservabilityRuntimeStatusResponse | None = None
) -> ObservabilityActivationReadinessResponse:
    runtime_status = (
        runtime_status if runtime_status is not None else build_observability_runtime_status()
    )
    audit_store = get_audit_store_runtime_status()
    access_control_runtime = build_access_control_runtime_status()

    blocking_findings: list[str] = []
    if settings.audit_store_mode != "sqlalchemy" or audit_store.status != "READY":
        blocking_findings.append(
            "Observability activation requires SQL-backed audit storage so incident evidence and caller-aware breakdowns remain restart-safe."
        )
    if (
        settings.access_control_store_mode != "sqlalchemy"
        or access_control_runtime.store.status != "READY"
    ):
        blocking_findings.append(
            "Observability activation requires SQL-backed caller-policy storage so tenant-aware breakdown visibility remains restart-safe and governed."
        )
    if runtime_status.unavailable_domain_count > 0:
        blocking_findings.append(
            "Observability activation is blocked while one or more summarized domains report unavailable telemetry posture."
        )
    if runtime_status.domain_count < 6:
        blocking_findings.append(
            "Observability activation is blocked until all six governed platform domains are covered by the bounded observability layer."
        )
    if runtime_status.incident_evidence_supported_domain_count < runtime_status.domain_count:
        blocking_findings.append(
            "Observability activation is blocked until every summarized domain exposes bounded incident evidence."
        )

    return ObservabilityActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        posture=runtime_status.posture,
        freshness=runtime_status.freshness,
        activation_ready=not blocking_findings,
        domain_count=runtime_status.domain_count,
        blocking_findings=blocking_findings,
        activation_path=[
            "Inspect `/platform/observability/runtime-status` to confirm all governed domains are covered and none are unavailable.",
            "Inspect `/platform/observability/incident-summary` and `/platform/observability/breakdowns` to confirm incident evidence and caller, tenant, and capability breakdowns are active.",
            "Use SQL-backed audit and caller-policy storage before treating observability evidence and authorized breakdown views as restart-safe governance surfaces.",
            "Approve rollout only when `/platform/observability/governance-status` and the embedded `observability_governance` block in `/platform/runtime-status` report the same posture.",
        ],
    )
