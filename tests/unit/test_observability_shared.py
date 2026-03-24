from app.contracts.observability import (
    ObservabilityBreakdownSupport,
    ObservabilityDomainId,
    ObservabilityFreshness,
    ObservabilityPosture,
)
from app.services.observability_shared import (
    assess_observability_posture,
    build_domain_telemetry_summary,
    build_incident_evidence_item,
)


def test_assess_observability_posture_reports_healthy_when_current() -> None:
    assessment = assess_observability_posture(source_available=True)

    assert assessment.posture == ObservabilityPosture.HEALTHY
    assert assessment.freshness == ObservabilityFreshness.CURRENT


def test_assess_observability_posture_reports_degraded_when_stale() -> None:
    assessment = assess_observability_posture(source_available=True, stale=True)

    assert assessment.posture == ObservabilityPosture.DEGRADED
    assert assessment.freshness == ObservabilityFreshness.STALE


def test_assess_observability_posture_reports_unavailable_when_source_missing() -> None:
    assessment = assess_observability_posture(source_available=False)

    assert assessment.posture == ObservabilityPosture.UNAVAILABLE
    assert assessment.freshness == ObservabilityFreshness.UNAVAILABLE


def test_build_domain_telemetry_summary_preserves_breakdown_and_findings() -> None:
    summary = build_domain_telemetry_summary(
        domain_id=ObservabilityDomainId.ASYNC,
        telemetry_sources=["async_runtime_status"],
        source_available=True,
        degraded_findings=["worker_unavailable"],
        stale=False,
        incident_evidence_supported=False,
        breakdown_support=ObservabilityBreakdownSupport(
            caller_app_supported=True,
            tenant_supported=False,
            capability_supported=True,
        ),
        incident_signal_count=1,
        summary=["Async worker fleet is degraded."],
    )

    assert summary.posture == ObservabilityPosture.DEGRADED
    assert summary.freshness == ObservabilityFreshness.CURRENT
    assert summary.breakdown_support.caller_app_supported is True
    assert summary.breakdown_support.tenant_supported is False
    assert summary.incident_signal_count == 1


def test_build_incident_evidence_item_can_report_durable_current_item() -> None:
    item = build_incident_evidence_item(
        domain_id=ObservabilityDomainId.SAFETY,
        evidence_id="safety_audit_evidence_pack",
        source_available=True,
        stale=False,
        degraded_findings=[],
        durable=True,
        summary="Safety evidence is durable.",
    )

    assert item.posture == ObservabilityPosture.HEALTHY
    assert item.freshness == ObservabilityFreshness.CURRENT
    assert item.durable is True
