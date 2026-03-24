from __future__ import annotations

from fastapi import APIRouter

from app.contracts.observability import ObservabilityRuntimeStatusResponse
from app.services.observability_runtime import build_observability_runtime_status

router = APIRouter(prefix="/platform/observability", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=ObservabilityRuntimeStatusResponse,
    operation_id="getObservabilityRuntimeStatus",
    summary="Get observability runtime status",
    description=(
        "Returns the bounded in-service observability posture for lotus-ai, including per-domain "
        "telemetry summaries and currently supported incident-evidence items."
    ),
    responses={
        200: {"description": "Observability runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_observability_runtime_status_route() -> ObservabilityRuntimeStatusResponse:
    return build_observability_runtime_status()
