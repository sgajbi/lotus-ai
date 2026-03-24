from __future__ import annotations

from dataclasses import dataclass

from app.contracts.observability import (
    DomainTelemetrySummary,
    IncidentEvidenceSummaryItem,
    ObservabilityBreakdownSupport,
    ObservabilityDomainId,
    ObservabilityFreshness,
    ObservabilityPosture,
)


@dataclass(frozen=True)
class ObservabilityAssessment:
    posture: ObservabilityPosture
    freshness: ObservabilityFreshness


def assess_observability_posture(
    *,
    source_available: bool,
    stale: bool = False,
    degraded_findings: list[str] | None = None,
) -> ObservabilityAssessment:
    findings = degraded_findings or []
    if not source_available:
        return ObservabilityAssessment(
            posture=ObservabilityPosture.UNAVAILABLE,
            freshness=ObservabilityFreshness.UNAVAILABLE,
        )
    if stale:
        return ObservabilityAssessment(
            posture=ObservabilityPosture.DEGRADED,
            freshness=ObservabilityFreshness.STALE,
        )
    if findings:
        return ObservabilityAssessment(
            posture=ObservabilityPosture.DEGRADED,
            freshness=ObservabilityFreshness.CURRENT,
        )
    return ObservabilityAssessment(
        posture=ObservabilityPosture.HEALTHY,
        freshness=ObservabilityFreshness.CURRENT,
    )


def build_domain_telemetry_summary(
    *,
    domain_id: ObservabilityDomainId,
    telemetry_sources: list[str],
    source_available: bool,
    degraded_findings: list[str],
    stale: bool,
    incident_evidence_supported: bool,
    breakdown_support: ObservabilityBreakdownSupport,
    incident_signal_count: int,
    summary: list[str],
) -> DomainTelemetrySummary:
    assessment = assess_observability_posture(
        source_available=source_available,
        stale=stale,
        degraded_findings=degraded_findings,
    )
    return DomainTelemetrySummary(
        domain_id=domain_id,
        posture=assessment.posture,
        freshness=assessment.freshness,
        telemetry_sources=telemetry_sources,
        incident_evidence_supported=incident_evidence_supported,
        incident_signal_count=incident_signal_count,
        breakdown_support=breakdown_support,
        status_summary=summary,
    )


def build_incident_evidence_item(
    *,
    domain_id: ObservabilityDomainId,
    evidence_id: str,
    source_available: bool,
    stale: bool,
    degraded_findings: list[str],
    durable: bool,
    summary: str,
) -> IncidentEvidenceSummaryItem:
    assessment = assess_observability_posture(
        source_available=source_available,
        stale=stale,
        degraded_findings=degraded_findings,
    )
    return IncidentEvidenceSummaryItem(
        domain_id=domain_id,
        evidence_id=evidence_id,
        posture=assessment.posture,
        freshness=assessment.freshness,
        durable=durable,
        summary=summary,
    )
