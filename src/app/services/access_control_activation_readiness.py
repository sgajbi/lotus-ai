from __future__ import annotations

from app.config import settings
from app.contracts.access_control import (
    AccessControlActivationReadinessResponse,
)
from app.services.access_control_runtime import (
    build_access_control_runtime_status,
    control_plane_authorization_enforced,
    data_plane_authorization_enforced,
)


def build_access_control_activation_readiness() -> AccessControlActivationReadinessResponse:
    runtime = build_access_control_runtime_status()
    blocking_findings: list[str] = []
    if settings.access_control_store_mode != "sqlalchemy":
        blocking_findings.append(
            "Full access-control activation requires SQL-backed caller policy storage so caller authorization remains restart-safe."
        )
    if not control_plane_authorization_enforced():
        blocking_findings.append(
            "Control-plane authorization must be enforced for async, prompt, and provider control actions before access-control rollout is fully activatable."
        )
    if not data_plane_authorization_enforced():
        blocking_findings.append(
            "Data-plane authorization must be enforced for task, retrieval, and live-provider request paths before access-control rollout is fully activatable."
        )
    activation_path = [
        "Keep the caller policy registry authoritative for all protected surfaces, including task execution, retrieval execution, live-provider execution, async control, prompt control, and provider control.",
        "Use SQL-backed caller policy storage before treating access-control enforcement as restart-safe platform governance.",
        "Inspect `/platform/access-control/runtime-status`, `/platform/access-control/governance-status`, and access-control-linked audit or control history after protected requests are blocked or allowed.",
        "Keep unknown callers fail-closed and avoid silent fallback from denied live or control-plane paths.",
    ]
    return AccessControlActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.access_control_store_mode,
        enforcement_state=runtime.enforcement_state,
        activation_ready=not blocking_findings,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
