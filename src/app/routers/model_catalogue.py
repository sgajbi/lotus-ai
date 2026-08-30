from __future__ import annotations

from fastapi import APIRouter

from app.contracts.model_catalogue import (
    ModelCatalogueEntryDetailResponse,
    ModelCatalogueResponse,
    ModelLifecycleTransitionRequest,
    ModelLifecycleTransitionResponse,
)
from app.services.model_catalogue import (
    apply_model_lifecycle_transition,
    build_model_catalogue_entry_detail,
    build_model_catalogue_response,
)

router = APIRouter(prefix="/platform/models", tags=["platform"])


@router.get(
    "/catalogue",
    response_model=ModelCatalogueResponse,
    operation_id="getModelCatalogue",
    summary="Get the governed model catalogue",
    description=(
        "Returns the governed model catalogue for lotus-ai: every configured model identity as "
        "a first-class entry with provider, family, exact revision, deployment, SKU, lifecycle "
        "state, approval evidence and pinning posture. Reads are idempotently reconciled with "
        "the configured live-text settings and the approved workflow-run model-risk inventory."
    ),
    responses={
        200: {"description": "Model catalogue returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_model_catalogue_route() -> ModelCatalogueResponse:
    return build_model_catalogue_response()


@router.get(
    "/catalogue/{entry_id}",
    response_model=ModelCatalogueEntryDetailResponse,
    operation_id="getModelCatalogueEntryDetail",
    summary="Get one model-catalogue entry with its lifecycle history",
    description=(
        "Returns one governed model-catalogue entry together with every recorded lifecycle "
        "transition, newest first - the durable evidence trail behind the entry's current state."
    ),
    responses={
        200: {"description": "Model-catalogue entry detail returned successfully."},
        404: {"description": "No entry exists for the given id."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_model_catalogue_entry_detail_route(
    entry_id: str,
) -> ModelCatalogueEntryDetailResponse:
    return build_model_catalogue_entry_detail(entry_id)


@router.post(
    "/catalogue/{entry_id}/lifecycle-transitions",
    response_model=ModelLifecycleTransitionResponse,
    operation_id="applyModelLifecycleTransition",
    summary="Apply a governed lifecycle transition to a catalogue entry",
    description=(
        "Moves one model-catalogue entry along the governed lifecycle edge table with a "
        "recorded reason, requester and approver. Promotion to APPROVED requires approval "
        "evidence. DEGRADED, DEPRECATED and RETIRED entries refuse new live executions at the "
        "provider gateway. Requires provider-control authorization and the durable catalogue "
        "store."
    ),
    responses={
        200: {"description": "Lifecycle transition applied."},
        403: {"description": "Caller is not authorized for provider control."},
        404: {"description": "No entry exists for the given id."},
        409: {"description": "The durable catalogue store is not configured."},
        422: {"description": "The transition is not allowed from the current state."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_model_lifecycle_transition_route(
    entry_id: str,
    request: ModelLifecycleTransitionRequest,
) -> ModelLifecycleTransitionResponse:
    return apply_model_lifecycle_transition(entry_id, request)
