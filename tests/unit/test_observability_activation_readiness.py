from pathlib import Path

from app.config import settings
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
from app.services.observability_activation_readiness import (
    build_observability_activation_readiness,
)
from app.services.observability_runtime import build_observability_runtime_status
from tests.support.migration_runner import upgrade_database_to_head


def test_observability_activation_readiness_blocks_without_durable_stores() -> None:
    settings.audit_store_mode = "memory"
    settings.access_control_store_mode = "memory"
    settings.database_url = None

    readiness = build_observability_activation_readiness()

    assert readiness.activation_ready is False
    assert any("SQL-backed audit storage" in item for item in readiness.blocking_findings)
    assert any("SQL-backed caller-policy storage" in item for item in readiness.blocking_findings)


def test_observability_activation_readiness_reports_sql_backed_posture_ready(
    tmp_path: Path,
) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'observability-activation.db'}"
    upgrade_database_to_head(settings.database_url)
    runtime_status = build_observability_runtime_status().model_copy(
        update={"ai_surface_supportability": _healthy_ai_surface_supportability_summary()}
    )

    readiness = build_observability_activation_readiness(runtime_status=runtime_status)

    assert readiness.activation_ready is True
    assert readiness.domain_count == 6
    assert readiness.blocking_findings == []


def test_observability_activation_readiness_blocks_no_sensitive_telemetry_degradation(
    tmp_path: Path,
) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'observability-ai-supportability.db'}"
    upgrade_database_to_head(settings.database_url)

    readiness = build_observability_activation_readiness()

    assert readiness.activation_ready is False
    assert any(
        "AI surface supportability reports degraded" in item for item in readiness.blocking_findings
    )
    assert any("no-sensitive-content telemetry" in item for item in readiness.blocking_findings)
    assert any("operator action" in item for item in readiness.blocking_findings)


def test_observability_activation_readiness_blocks_action_required_ai_surface(
    tmp_path: Path,
) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'observability-ai-action-required.db'}"
    upgrade_database_to_head(settings.database_url)
    runtime_status = build_observability_runtime_status().model_copy(
        update={"ai_surface_supportability": _action_required_ai_surface_supportability_summary()}
    )

    readiness = build_observability_activation_readiness(runtime_status=runtime_status)

    assert readiness.activation_ready is False
    assert any(
        "AI surface supportability reports degraded" in item for item in readiness.blocking_findings
    )
    assert any("operator action" in item for item in readiness.blocking_findings)
    assert all("raw prompt" not in item.lower() for item in readiness.blocking_findings)


def _healthy_ai_surface_supportability_summary() -> AISurfaceSupportabilitySummary:
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


def _action_required_ai_surface_supportability_summary() -> AISurfaceSupportabilitySummary:
    summary = _healthy_ai_surface_supportability_summary()
    action_required_surface = summary.surfaces[0].model_copy(
        update={
            "supportability_status": "ACTION_REQUIRED",
            "supportability_reason": AISurfaceSupportabilityReason.WORKFLOW_PACK_ACTION_REQUIRED,
        }
    )
    return summary.model_copy(
        update={
            "posture": ObservabilityPosture.DEGRADED,
            "action_required_surface_count": 1,
            "surfaces": [action_required_surface, *summary.surfaces[1:]],
            "status_summary": [
                "No-sensitive-content telemetry is active across represented AI-backed surfaces.",
                "One represented AI-backed surface currently requires operator action.",
            ],
        }
    )
