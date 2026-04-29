from __future__ import annotations

from prometheus_client import Gauge

from app.contracts.observability import (
    AISurfaceSupportabilityItem,
    AISurfaceSupportabilitySummary,
    ObservabilityFreshness,
    ObservabilityPosture,
)
from app.contracts.workflow_packs import WorkflowPackExecutableActivitySummaryResponse
from app.services.provider_operations_status import build_provider_operations_status
from app.services.safety_status import build_safety_runtime_status
from app.services.workflow_pack_runtime_status import build_workflow_pack_runtime_status_summary

AI_SURFACE_SUPPORTABILITY_METRIC = "lotus_ai_surface_supportability_state"

_AI_SURFACE_SUPPORTABILITY_GAUGE = Gauge(
    AI_SURFACE_SUPPORTABILITY_METRIC,
    "Bounded AI-backed surface supportability posture by surface and source.",
    ["surface", "posture", "source"],
)

_WORKFLOW_PACK_SURFACE_OWNERS = {
    "advisor_brief.pack@v1": (
        "advisor_brief",
        "lotus-advise",
        "lotus-advise",
    ),
    "twr_inspection_support_brief.pack@v1": (
        "twr_inspection_support_brief",
        "lotus-performance",
        "lotus-performance",
    ),
    "workspace_rationale.pack@v1": (
        "workspace_rationale",
        "lotus-workbench",
        "lotus-workbench",
    ),
}

_PROMETHEUS_POSTURES = (
    ObservabilityPosture.HEALTHY,
    ObservabilityPosture.DEGRADED,
    ObservabilityPosture.UNAVAILABLE,
)


def build_ai_surface_supportability_summary() -> AISurfaceSupportabilitySummary:
    workflow_pack_runtime = build_workflow_pack_runtime_status_summary()
    provider_operations = build_provider_operations_status()
    safety_runtime = build_safety_runtime_status()

    provider_posture = _provider_observability_posture(
        operations_state=provider_operations.operations_state.value
    )
    no_sensitive_content_telemetry = safety_runtime.runtime_redaction_active
    surfaces = [
        _build_surface_item(
            activity=activity,
            provider_posture=provider_posture,
            no_sensitive_content_telemetry=no_sensitive_content_telemetry,
        )
        for activity in workflow_pack_runtime.executable_activity
    ]
    action_required_surface_count = sum(
        1 for surface in surfaces if surface.supportability_status == "ACTION_REQUIRED"
    )
    unavailable_surface_count = sum(
        1 for surface in surfaces if surface.supportability_status == "UNAVAILABLE"
    )
    posture = _overall_posture(
        surfaces=surfaces,
        no_sensitive_content_telemetry=no_sensitive_content_telemetry,
        provider_posture=provider_posture,
    )
    _record_supportability_metric(surfaces=surfaces)
    return AISurfaceSupportabilitySummary(
        posture=posture,
        freshness=(
            ObservabilityFreshness.UNAVAILABLE
            if unavailable_surface_count
            else ObservabilityFreshness.CURRENT
        ),
        supported_surface_count=len(surfaces),
        executable_workflow_pack_count=workflow_pack_runtime.executable_registration_count,
        action_required_surface_count=action_required_surface_count,
        unavailable_surface_count=unavailable_surface_count,
        no_sensitive_content_telemetry=no_sensitive_content_telemetry,
        metric_name=AI_SURFACE_SUPPORTABILITY_METRIC,
        surfaces=surfaces,
        status_summary=[
            f"AI surface supportability is sourced from {len(surfaces)} executable workflow-pack surface(s), provider operations, and safety runtime.",
            (
                "No-sensitive-content telemetry is active across represented AI-backed surfaces."
                if no_sensitive_content_telemetry
                else "No-sensitive-content telemetry remains degraded until runtime redaction and rollout observability are both ready."
            ),
            (
                f"{action_required_surface_count} represented surface(s) currently require operator action."
                if action_required_surface_count
                else "Represented AI-backed surfaces currently expose no run-ledger action-required posture."
            ),
        ],
    )


def _build_surface_item(
    *,
    activity: WorkflowPackExecutableActivitySummaryResponse,
    provider_posture: ObservabilityPosture,
    no_sensitive_content_telemetry: bool,
) -> AISurfaceSupportabilityItem:
    surface_id, owning_service, workflow_authority_owner = _WORKFLOW_PACK_SURFACE_OWNERS.get(
        activity.registration_ref,
        (activity.pack_id, "lotus-ai", "caller-owned"),
    )
    supportability_status = _surface_supportability_status(
        has_activity=activity.has_activity,
        action_required_count=activity.action_required_count,
        ready_count=activity.ready_count,
        no_sensitive_content_telemetry=no_sensitive_content_telemetry,
    )
    return AISurfaceSupportabilityItem(
        surface_id=surface_id,
        owning_service=owning_service,
        workflow_authority_owner=workflow_authority_owner,
        workflow_pack_ref=activity.registration_ref,
        supportability_status=supportability_status,
        model_posture=provider_posture,
        latest_ready_run_id=activity.latest_ready_run_id,
        latest_action_required_run_id=activity.latest_action_required_run_id,
        no_sensitive_content_telemetry=no_sensitive_content_telemetry,
        source_endpoints=[
            "/platform/runtime-status",
            "/platform/observability/runtime-status",
            "/platform/workflow-packs/runs",
            "/platform/safety/runtime-status",
            "/platform/providers/operations-status",
        ],
        status_summary=[
            f"{surface_id} is grounded in workflow-pack runtime source `{activity.registration_ref}`.",
            (
                "Run-ledger evidence is present for this surface."
                if activity.has_activity
                else "No run-ledger activity has been recorded for this surface yet."
            ),
            (
                "The surface is covered by bounded no-sensitive-content telemetry."
                if no_sensitive_content_telemetry
                else "The surface remains degraded until no-sensitive-content telemetry is fully active."
            ),
        ],
    )


def _provider_observability_posture(*, operations_state: str) -> ObservabilityPosture:
    if operations_state in {"AVAILABLE", "CANARY_ACTIVE"}:
        return ObservabilityPosture.HEALTHY
    if operations_state in {"CIRCUIT_OPEN", "DEGRADED"}:
        return ObservabilityPosture.DEGRADED
    return ObservabilityPosture.DEGRADED


def _surface_supportability_status(
    *,
    has_activity: bool,
    action_required_count: int,
    ready_count: int,
    no_sensitive_content_telemetry: bool,
) -> str:
    if not no_sensitive_content_telemetry:
        return "ACTION_REQUIRED"
    if action_required_count:
        return "ACTION_REQUIRED"
    if ready_count:
        return "READY"
    if has_activity:
        return "HISTORICAL"
    return "SUPPORTED_NO_ACTIVITY"


def _overall_posture(
    *,
    surfaces: list[AISurfaceSupportabilityItem],
    no_sensitive_content_telemetry: bool,
    provider_posture: ObservabilityPosture,
) -> ObservabilityPosture:
    if not surfaces:
        return ObservabilityPosture.UNAVAILABLE
    if provider_posture is ObservabilityPosture.UNAVAILABLE:
        return ObservabilityPosture.UNAVAILABLE
    if (
        not no_sensitive_content_telemetry
        or provider_posture is ObservabilityPosture.DEGRADED
        or any(surface.supportability_status == "ACTION_REQUIRED" for surface in surfaces)
    ):
        return ObservabilityPosture.DEGRADED
    return ObservabilityPosture.HEALTHY


def _record_supportability_metric(*, surfaces: list[AISurfaceSupportabilityItem]) -> None:
    for surface in surfaces:
        surface_posture = (
            ObservabilityPosture.HEALTHY
            if surface.supportability_status in {"READY", "SUPPORTED_NO_ACTIVITY", "HISTORICAL"}
            else ObservabilityPosture.DEGRADED
        )
        for posture in _PROMETHEUS_POSTURES:
            _AI_SURFACE_SUPPORTABILITY_GAUGE.labels(
                surface=surface.surface_id,
                posture=posture.value,
                source="workflow_pack_runtime",
            ).set(1 if posture is surface_posture else 0)
