from app.contracts.observability import (
    AISurfaceSupportabilityReason,
    AISurfaceSupportabilitySummary,
    ObservabilityFreshness,
    ObservabilityPosture,
)
from app.services.ai_surface_supportability import (
    AI_SURFACE_SUPPORTABILITY_METRIC,
    AI_SURFACE_SUPPORTABILITY_METRIC_LABELS,
    build_ai_surface_supportability_summary,
)


def build_healthy_ai_surface_supportability_summary() -> AISurfaceSupportabilitySummary:
    summary = build_ai_surface_supportability_summary()
    healthy_surfaces = [
        surface.model_copy(
            update={
                "supportability_status": "READY",
                "supportability_reason": AISurfaceSupportabilityReason.WORKFLOW_PACK_READY,
                "no_sensitive_content_telemetry": True,
            }
        )
        for surface in summary.surfaces
    ]
    return summary.model_copy(
        update={
            "posture": ObservabilityPosture.HEALTHY,
            "freshness": ObservabilityFreshness.CURRENT,
            "action_required_surface_count": 0,
            "unavailable_surface_count": 0,
            "no_sensitive_content_telemetry": True,
            "metric_name": AI_SURFACE_SUPPORTABILITY_METRIC,
            "metric_labels": list(AI_SURFACE_SUPPORTABILITY_METRIC_LABELS),
            "surfaces": healthy_surfaces,
            "status_summary": [
                "No-sensitive-content telemetry is active across represented AI-backed surfaces.",
                "Represented AI-backed surfaces currently expose ready workflow-pack posture.",
            ],
        }
    )
