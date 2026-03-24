from __future__ import annotations

from app.config import settings
from app.contracts.observability import (
    ObservabilityIncidentSummaryResponse,
    ObservabilityPosture,
)
from app.services.observability_domain_summaries import build_slice_two_observability_bundles


def build_observability_incident_summary() -> ObservabilityIncidentSummaryResponse:
    bundles = build_slice_two_observability_bundles()
    summaries = [bundle.summary for bundle in bundles]
    degraded_domain_count = sum(
        1
        for summary in summaries
        if summary.telemetry.posture == ObservabilityPosture.DEGRADED
    )
    return ObservabilityIncidentSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        domain_count=len(summaries),
        degraded_domain_count=degraded_domain_count,
        summaries=summaries,
        status_summary=[
            "Incident summary currently covers provider, retrieval, and async domains with bounded runtime-backed evidence.",
            (
                f"{degraded_domain_count} domain(s) currently expose degraded operational posture."
                if degraded_domain_count
                else "Current provider, retrieval, and async domains are not exposing degraded posture."
            ),
        ],
    )
