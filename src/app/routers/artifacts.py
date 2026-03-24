from __future__ import annotations

from fastapi import APIRouter

from app.contracts.artifacts import ArtifactRuntimeStatusResponse
from app.services.artifact_runtime import build_artifact_runtime_status

router = APIRouter(prefix="/platform/artifacts", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=ArtifactRuntimeStatusResponse,
    operation_id="getArtifactRuntimeStatus",
    summary="Get artifact storage runtime status",
    description=(
        "Returns the governed artifact metadata and object-store posture for lotus-ai, including "
        "bounded status for the relational metadata layer and configured payload-store backend."
    ),
    responses={
        200: {"description": "Artifact runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_artifact_runtime_status_route() -> ArtifactRuntimeStatusResponse:
    return build_artifact_runtime_status()
