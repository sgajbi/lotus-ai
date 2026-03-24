from __future__ import annotations

from app.config import settings
from app.contracts.observability import (
    DomainTelemetrySummary,
    IncidentEvidenceSummaryItem,
    ObservabilityBreakdownSupport,
    ObservabilityDomainId,
    ObservabilityFreshness,
    ObservabilityPosture,
    ObservabilityRuntimeStatusResponse,
)
from app.contracts.safety import SafetyExecutionDisposition
from app.services.observability_domain_summaries import build_slice_two_observability_bundles
from app.services.observability_shared import (
    assess_observability_posture,
    build_domain_telemetry_summary,
    build_incident_evidence_item,
)
from app.services.prompt_status import build_prompt_runtime_status
from app.services.safety_status import build_safety_runtime_status


def build_observability_runtime_status() -> ObservabilityRuntimeStatusResponse:
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
        degraded_findings=[] if degraded_domain_count == 0 else ["partial_domain_coverage"],
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
        status_summary=_build_status_summary(
            healthy_domain_count=healthy_domain_count,
            degraded_domain_count=degraded_domain_count,
            unavailable_domain_count=unavailable_domain_count,
            incident_evidence_supported_domain_count=incident_evidence_supported_domain_count,
        ),
    )


def _build_domain_summaries() -> list[DomainTelemetrySummary]:
    bundles = build_slice_two_observability_bundles()
    prompt_runtime = build_prompt_runtime_status()
    safety_runtime = build_safety_runtime_status()
    domains = [bundle.summary.telemetry for bundle in bundles]
    domains.extend(
        [
            build_domain_telemetry_summary(
                domain_id=ObservabilityDomainId.EVALUATION,
                telemetry_sources=["evaluation_runtime_status", "evaluation_runtime_store"],
                source_available=True,
                degraded_findings=[],
                stale=False,
                incident_evidence_supported=False,
                breakdown_support=ObservabilityBreakdownSupport(
                    caller_app_supported=True,
                    tenant_supported=False,
                    capability_supported=True,
                ),
                incident_signal_count=0,
                summary=[
                    "Evaluation observability currently reuses runtime-backed run and approval-gate summaries.",
                    "Dedicated incident-evidence summaries for stale or failing approval posture are not yet rolled out.",
                ],
            ),
            build_domain_telemetry_summary(
                domain_id=ObservabilityDomainId.PROMPT,
                telemetry_sources=["prompt_runtime_status", "prompt_control_history"],
                source_available=True,
                degraded_findings=[],
                stale=False,
                incident_evidence_supported=False,
                breakdown_support=ObservabilityBreakdownSupport(
                    caller_app_supported=True,
                    tenant_supported=False,
                    capability_supported=True,
                ),
                incident_signal_count=prompt_runtime.candidate_prompt_count,
                summary=[
                    "Prompt observability currently reuses rollout-state selection and control-history data.",
                    "Dedicated incident-evidence summaries for blocked promotions and rollback posture are not yet rolled out.",
                ],
            ),
            build_domain_telemetry_summary(
                domain_id=ObservabilityDomainId.SAFETY,
                telemetry_sources=["safety_runtime_status", "audit_repository", "execution_evidence"],
                source_available=True,
                degraded_findings=_safety_findings(safety_runtime),
                stale=False,
                incident_evidence_supported=True,
                breakdown_support=ObservabilityBreakdownSupport(
                    caller_app_supported=True,
                    tenant_supported=True,
                    capability_supported=True,
                ),
                incident_signal_count=0,
                summary=[
                    "Safety observability already has bounded durable evidence through audit and execution-evidence records.",
                    "A unified observability incident view for blocked, degraded, and redacted outcomes is not yet rolled out.",
                ],
            ),
        ]
    )
    return domains


def _build_incident_items() -> list[IncidentEvidenceSummaryItem]:
    items = [
        item
        for bundle in build_slice_two_observability_bundles()
        for item in bundle.summary.incident_evidence_items
    ]
    items.append(
        build_incident_evidence_item(
            domain_id=ObservabilityDomainId.SAFETY,
            evidence_id="safety_audit_evidence_pack",
            source_available=True,
            stale=False,
            degraded_findings=[],
            durable=True,
            summary="Safety audit and execution evidence is already durable and correlation-backed.",
        )
    )
    return items


def _safety_findings(safety_runtime: object) -> list[str]:
    findings: list[str] = []
    if (
        getattr(safety_runtime, "runtime_redaction_disposition", None)
        == SafetyExecutionDisposition.DOCUMENTED_ONLY
    ):
        findings.append("safety_runtime_redaction_not_active")
    return findings


def _build_status_summary(
    *,
    healthy_domain_count: int,
    degraded_domain_count: int,
    unavailable_domain_count: int,
    incident_evidence_supported_domain_count: int,
) -> list[str]:
    return [
        f"Observability runtime currently summarizes {healthy_domain_count + degraded_domain_count + unavailable_domain_count} governed domains through bounded in-service contracts.",
        (
            f"{degraded_domain_count} domain(s) remain in degraded observability posture because the unified incident-evidence rollout is still partial."
            if degraded_domain_count
            else "All summarized domains currently report healthy observability posture."
        ),
        f"{incident_evidence_supported_domain_count} domain(s) already expose bounded incident evidence.",
    ]
