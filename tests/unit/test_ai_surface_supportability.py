import json
import re

from prometheus_client import generate_latest

from app.contracts.observability import ObservabilityPosture
from app.services.ai_surface_supportability import (
    AI_SURFACE_SUPPORTABILITY_METRIC,
    AI_SURFACE_SUPPORTABILITY_METRIC_LABELS,
    _overall_posture,
    _provider_observability_posture,
    _surface_supportability_reason,
    _surface_supportability_status,
    build_ai_surface_supportability_summary,
)


FORBIDDEN_SUPPORTABILITY_TOKENS = {
    "account_id",
    "advisor_id",
    "client_id",
    "correlation_id",
    "model_output",
    "portfolio_id",
    "raw_prompt",
    "request_body",
    "response_body",
    "trace_id",
}


def test_ai_surface_supportability_summary_is_source_backed_and_bounded() -> None:
    summary = build_ai_surface_supportability_summary()

    assert summary.posture == ObservabilityPosture.DEGRADED
    assert summary.supported_surface_count == 6
    assert summary.executable_workflow_pack_count == 6
    assert summary.action_required_surface_count == 6
    assert summary.unavailable_surface_count == 0
    assert summary.no_sensitive_content_telemetry is False
    assert summary.metric_name == "lotus_ai_surface_supportability_state"
    assert summary.metric_labels == list(AI_SURFACE_SUPPORTABILITY_METRIC_LABELS)
    assert {item.surface_id: item.owning_service for item in summary.surfaces} == {
        "advisor_brief": "lotus-advise",
        "dpm_pm_memo": "lotus-manage",
        "dpm_wave_pm_memo": "lotus-manage",
        "outcome_review_narrative": "lotus-manage",
        "twr_inspection_support_brief": "lotus-performance",
        "workspace_rationale": "lotus-workbench",
    }
    assert (
        next(
            item for item in summary.surfaces if item.surface_id == "outcome_review_narrative"
        ).workflow_authority_owner
        == "lotus-manage"
    )
    assert {item.supportability_reason.value for item in summary.surfaces} == {
        "NO_SENSITIVE_TELEMETRY_DEGRADED"
    }
    assert all(item.workflow_authority_owner != "lotus-ai" for item in summary.surfaces)
    assert all(
        "/platform/workflow-packs/runs" in item.source_endpoints for item in summary.surfaces
    )
    assert any("No-sensitive-content telemetry" in line for line in summary.status_summary)


def test_ai_surface_supportability_payload_excludes_sensitive_diagnostics() -> None:
    summary = build_ai_surface_supportability_summary()

    payload = json.dumps(summary.model_dump(mode="json"), sort_keys=True)

    assert not (FORBIDDEN_SUPPORTABILITY_TOKENS & set(re.findall(r'"([^"]+)":', payload)))
    assert all(token not in payload for token in FORBIDDEN_SUPPORTABILITY_TOKENS)


def test_ai_surface_supportability_metric_uses_only_governed_labels() -> None:
    summary = build_ai_surface_supportability_summary()
    metrics_payload = generate_latest().decode("utf-8")

    metric_lines = [
        line
        for line in metrics_payload.splitlines()
        if line.startswith(f"{AI_SURFACE_SUPPORTABILITY_METRIC}{{")
    ]

    assert metric_lines
    assert all(surface.surface_id in metrics_payload for surface in summary.surfaces)
    for line in metric_lines:
        labels = line.split("{", 1)[1].split("}", 1)[0]
        label_keys = {part.split("=", 1)[0] for part in labels.split(",")}
        assert label_keys == set(AI_SURFACE_SUPPORTABILITY_METRIC_LABELS)
        assert not (label_keys & FORBIDDEN_SUPPORTABILITY_TOKENS)


def test_ai_surface_supportability_classifies_ready_historical_and_provider_postures() -> None:
    assert (
        _provider_observability_posture(operations_state="AVAILABLE")
        is ObservabilityPosture.HEALTHY
    )
    assert (
        _provider_observability_posture(operations_state="CIRCUIT_OPEN")
        is ObservabilityPosture.DEGRADED
    )

    assert (
        _surface_supportability_status(
            has_activity=True,
            action_required_count=1,
            ready_count=0,
            no_sensitive_content_telemetry=True,
        )
        == "ACTION_REQUIRED"
    )
    assert (
        _surface_supportability_status(
            has_activity=True,
            action_required_count=0,
            ready_count=1,
            no_sensitive_content_telemetry=True,
        )
        == "READY"
    )
    assert (
        _surface_supportability_status(
            has_activity=True,
            action_required_count=0,
            ready_count=0,
            no_sensitive_content_telemetry=True,
        )
        == "HISTORICAL"
    )
    assert (
        _surface_supportability_reason(
            has_activity=True,
            action_required_count=1,
            ready_count=0,
            no_sensitive_content_telemetry=True,
        ).value
        == "WORKFLOW_PACK_ACTION_REQUIRED"
    )
    assert (
        _surface_supportability_reason(
            has_activity=True,
            action_required_count=0,
            ready_count=1,
            no_sensitive_content_telemetry=True,
        ).value
        == "WORKFLOW_PACK_READY"
    )
    assert (
        _surface_supportability_reason(
            has_activity=True,
            action_required_count=0,
            ready_count=0,
            no_sensitive_content_telemetry=True,
        ).value
        == "WORKFLOW_PACK_HISTORICAL"
    )

    summary = build_ai_surface_supportability_summary()
    healthy_surfaces = [
        surface.model_copy(update={"supportability_status": "READY"})
        for surface in summary.surfaces
    ]
    assert (
        _overall_posture(
            surfaces=[],
            no_sensitive_content_telemetry=True,
            provider_posture=ObservabilityPosture.HEALTHY,
        )
        is ObservabilityPosture.UNAVAILABLE
    )
    assert (
        _overall_posture(
            surfaces=healthy_surfaces,
            no_sensitive_content_telemetry=True,
            provider_posture=ObservabilityPosture.UNAVAILABLE,
        )
        is ObservabilityPosture.UNAVAILABLE
    )
    assert (
        _overall_posture(
            surfaces=healthy_surfaces,
            no_sensitive_content_telemetry=True,
            provider_posture=ObservabilityPosture.HEALTHY,
        )
        is ObservabilityPosture.HEALTHY
    )
