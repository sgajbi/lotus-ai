from __future__ import annotations

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselineActivationReadinessResponse,
)
from app.services.production_baseline_runtime import build_production_baseline_runtime_status


def build_production_baseline_activation_readiness(
    app_state: object | None = None,
    *,
    runtime_status: object | None = None,
) -> ProductionBaselineActivationReadinessResponse:
    runtime_status = (
        runtime_status
        if runtime_status is not None
        else build_production_baseline_runtime_status(app_state)
    )
    activation_path = [
        "Use PostgreSQL-backed durable store seams for audit, prompts, retrieval metadata, access control, provider operations, async runtime, evaluation runtime, and artifact metadata.",
        "Keep Redis queue delivery and dedicated-worker execution active for allowlisted async job types before treating the runtime as production-shaped.",
        "Move artifact payload storage to a governed production object-store backend instead of memory or filesystem fallback modes.",
        "Inject live-provider and other production secrets through deployment-managed secret handling rather than local project files.",
        "Treat successful live-provider execution and successful Docker bring-up as supporting evidence only; production activation still depends on the full runtime baseline and its governance surfaces.",
    ]
    return ProductionBaselineActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        posture=runtime_status.posture,
        prod_shaped_local=runtime_status.prod_shaped_local,
        production_ready=runtime_status.production_ready,
        activation_ready=runtime_status.production_ready,
        blocking_findings=runtime_status.blocking_findings,
        activation_path=activation_path,
    )
