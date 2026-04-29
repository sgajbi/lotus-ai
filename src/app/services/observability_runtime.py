from __future__ import annotations

from app.config import settings
from app.contracts.observability import (
    DomainTelemetrySummary,
    IncidentEvidenceSummaryItem,
    ObservabilityFreshness,
    ObservabilityPosture,
    ObservabilityRuntimeStatusResponse,
)
from app.services.deployment_split_runtime import build_deployment_split_runtime_status
from app.services.ai_surface_supportability import build_ai_surface_supportability_summary
from app.services.observability_domain_summaries import build_current_observability_bundles
from app.services.observability_shared import assess_observability_posture


def build_observability_runtime_status() -> ObservabilityRuntimeStatusResponse:
    deployment_split = build_deployment_split_runtime_status()
    ai_surface_supportability = build_ai_surface_supportability_summary()
    domains = _build_domain_summaries()
    incident_items = _build_incident_items()
    postures = [domain.posture for domain in domains]
    freshness_states = [domain.freshness for domain in domains]
    healthy_domain_count = sum(1 for posture in postures if posture == ObservabilityPosture.HEALTHY)
    degraded_domain_count = sum(
        1 for posture in postures if posture == ObservabilityPosture.DEGRADED
    )
    unavailable_domain_count = sum(
        1 for posture in postures if posture == ObservabilityPosture.UNAVAILABLE
    )
    incident_evidence_supported_domain_count = sum(
        1 for domain in domains if domain.incident_evidence_supported
    )
    overall_assessment = assess_observability_posture(
        source_available=unavailable_domain_count == 0,
        stale=any(state == ObservabilityFreshness.STALE for state in freshness_states),
        degraded_findings=[] if degraded_domain_count == 0 else ["degraded_domain_posture"],
    )
    return ObservabilityRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        posture=overall_assessment.posture,
        freshness=overall_assessment.freshness,
        domain_count=len(domains),
        healthy_domain_count=healthy_domain_count,
        degraded_domain_count=degraded_domain_count,
        unavailable_domain_count=unavailable_domain_count,
        incident_evidence_supported_domain_count=incident_evidence_supported_domain_count,
        domains=domains,
        incident_evidence_items=incident_items,
        ai_surface_supportability=ai_surface_supportability,
        status_summary=_build_status_summary(
            deployment_split_summary=deployment_split.status_summary[0],
            deployment_split_degraded=deployment_split.degraded,
            ai_surface_supportability_posture=ai_surface_supportability.posture.value,
            healthy_domain_count=healthy_domain_count,
            degraded_domain_count=degraded_domain_count,
            unavailable_domain_count=unavailable_domain_count,
            incident_evidence_supported_domain_count=incident_evidence_supported_domain_count,
        ),
    )


def _build_domain_summaries() -> list[DomainTelemetrySummary]:
    return [bundle.summary.telemetry for bundle in build_current_observability_bundles()]


def _build_incident_items() -> list[IncidentEvidenceSummaryItem]:
    items = [
        item
        for bundle in build_current_observability_bundles()
        for item in bundle.summary.incident_evidence_items
    ]
    return items


def _build_status_summary(
    *,
    deployment_split_summary: str,
    deployment_split_degraded: bool,
    ai_surface_supportability_posture: str,
    healthy_domain_count: int,
    degraded_domain_count: int,
    unavailable_domain_count: int,
    incident_evidence_supported_domain_count: int,
) -> list[str]:
    return [
        f"Observability runtime currently summarizes {healthy_domain_count + degraded_domain_count + unavailable_domain_count} governed domains through bounded in-service contracts.",
        (
            f"Deployment-split posture: {deployment_split_summary.lower()}"
            if not deployment_split_degraded
            else f"Deployment-split posture is active but degraded: {deployment_split_summary.lower()}"
        ),
        f"AI surface supportability currently reports `{ai_surface_supportability_posture}` posture from workflow-pack runtime, provider, and safety sources.",
        (
            f"{degraded_domain_count} domain(s) currently report degraded observability posture because the underlying governed runtime or evidence state is degraded."
            if degraded_domain_count
            else "All summarized domains currently report healthy observability posture."
        ),
        f"{incident_evidence_supported_domain_count} domain(s) already expose bounded incident evidence.",
    ]
