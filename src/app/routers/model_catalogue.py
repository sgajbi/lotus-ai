from __future__ import annotations

from fastapi import APIRouter

from app.contracts.governed_actions import GovernedActionResponse
from app.contracts.model_catalogue import (
    ModelCapabilityDegradationRequest,
    ModelCapabilityDegradationResponse,
    ModelCapabilityRestoreApprovalRequest,
    ModelCapabilityRestoreApprovalResponse,
    ModelCapabilityRestoreIntentRequest,
    ModelCatalogueEntryDetailResponse,
    ModelCatalogueResponse,
    ModelLifecycleTransitionRequest,
    ModelLifecycleTransitionResponse,
    ModelPromotionApprovalRequest,
    ModelPromotionApprovalResponse,
    ModelPromotionIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.model_catalogue import (
    apply_model_lifecycle_transition,
    approve_model_capability_restore,
    approve_model_promotion,
    build_model_catalogue_entry_detail,
    build_model_catalogue_response,
    degrade_model_capability,
    request_model_capability_restore,
    request_model_promotion,
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
    summary="Apply a single-principal lifecycle transition to a catalogue entry",
    description=(
        "Moves one model-catalogue entry along the governed lifecycle edge table with a "
        "recorded reason, under the caller's verified identity (issue #245). Safety and "
        "administrative targets only: serving promotions (APPROVED, SHADOW, CANARY, "
        "PRODUCTION) are refused here and go through the governed two-step promotion flow. "
        "DEGRADED, DEPRECATED and RETIRED entries refuse new live executions at the provider "
        "gateway. Requires provider-control authorization and the durable catalogue store."
    ),
    responses={
        200: {"description": "Lifecycle transition applied."},
        403: {"description": "Caller is not authorized for provider control."},
        404: {"description": "No entry exists for the given id."},
        409: {
            "description": "The durable catalogue store is not configured, or the target "
            "expands serving posture and requires the governed promotion flow."
        },
        422: {"description": "The transition is not allowed from the current state."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_model_lifecycle_transition_route(
    entry_id: str,
    request: ModelLifecycleTransitionRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ModelLifecycleTransitionResponse:
    return apply_model_lifecycle_transition(entry_id, request, authenticated_caller)


@router.post(
    "/catalogue/{entry_id}/promotion-requests",
    response_model=GovernedActionResponse,
    operation_id="requestModelPromotion",
    summary="Request a serving promotion of a catalogue entry",
    description=(
        "Step one of governed serving promotion (issue #245): validates the target, the "
        "lifecycle edge and the named PASS-verdict evaluation run, then records a pending "
        "intent under the requester's verified credential and returns the action hash a "
        "distinct verified credential must approve. Eval evidence enables the decision; it "
        "does not make the decision. The entry is unchanged until the approval executes."
    ),
    responses={
        200: {"description": "Promotion intent recorded and pending approval."},
        403: {
            "description": "Caller is not authorized for provider control, or carries no "
            "verified credential."
        },
        404: {"description": "No entry exists for the given id."},
        409: {"description": "The durable catalogue store is not configured."},
        422: {
            "description": "The target is not a serving promotion, the edge is not allowed, "
            "or the evaluation run is missing or did not pass."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def request_model_promotion_route(
    entry_id: str,
    request: ModelPromotionIntentRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> GovernedActionResponse:
    return request_model_promotion(entry_id, request, authenticated_caller)


@router.post(
    "/catalogue/{entry_id}/promotion-approvals",
    response_model=ModelPromotionApprovalResponse,
    operation_id="approveModelPromotion",
    summary="Approve and execute a pending serving promotion",
    description=(
        "Step two of governed serving promotion (issue #245): a verified credential DISTINCT "
        "from the requester's approves the exact pending action hash, which re-validates the "
        "lifecycle edge and eval evidence, executes the promotion, and records the full "
        "request-approval-execution evidence chain. A lifecycle-state or revision change "
        "since the request refuses the stale approval."
    ),
    responses={
        200: {"description": "Promotion executed under governed approval."},
        403: {
            "description": "Caller is not authorized, carries no verified credential, or is "
            "the same credential that requested the action."
        },
        404: {"description": "No entry or no pending action exists for the given id."},
        409: {
            "description": "The durable catalogue store is not configured, the action hash "
            "does not match, or the entry changed since the request and the approval is stale."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def approve_model_promotion_route(
    entry_id: str,
    request: ModelPromotionApprovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ModelPromotionApprovalResponse:
    return approve_model_promotion(entry_id, request, authenticated_caller)


@router.post(
    "/catalogue/{entry_id}/capability-degradations",
    response_model=ModelCapabilityDegradationResponse,
    operation_id="degradeModelCapability",
    summary="Degrade one capability dimension on a catalogue entry",
    description=(
        "Records an observed regression scoped to one capability dimension (issue #245, "
        "slice 2): requirement routing refuses that capability as CAPABILITY_DEGRADED while "
        "the model stays in service for everything else, and the underlying assessed fact is "
        "never rewritten. Safety direction: applied immediately by one verified principal, "
        "no approval step. Requires provider-control authorization and the durable catalogue "
        "store."
    ),
    responses={
        200: {"description": "Capability degraded immediately."},
        403: {"description": "Caller is not authorized for provider control."},
        404: {"description": "No entry exists for the given id."},
        409: {
            "description": "The durable catalogue store is not configured, or the capability "
            "is already degraded."
        },
        422: {"description": "The dimension is not one requirement routing enforces."},
        500: {"description": "Unexpected server error."},
    },
)
async def degrade_model_capability_route(
    entry_id: str,
    request: ModelCapabilityDegradationRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ModelCapabilityDegradationResponse:
    return degrade_model_capability(entry_id, request, authenticated_caller)


@router.post(
    "/catalogue/{entry_id}/capability-restore-requests",
    response_model=GovernedActionResponse,
    operation_id="requestModelCapabilityRestore",
    summary="Request restore of a degraded capability",
    description=(
        "Step one of governed capability restore (issue #245, slice 2): clearing a "
        "degradation re-exposes the underlying evidence-derived fact to requirement routing, "
        "so the restore is validated (active degradation, PASS-verdict evaluation run) and "
        "recorded as a pending intent a distinct verified credential must approve. The "
        "capability stays degraded until the approval executes."
    ),
    responses={
        200: {"description": "Restore intent recorded and pending approval."},
        403: {
            "description": "Caller is not authorized for provider control, or carries no "
            "verified credential."
        },
        404: {"description": "No entry exists for the given id."},
        409: {
            "description": "The durable catalogue store is not configured, or the capability "
            "is not degraded."
        },
        422: {"description": "The evaluation run is missing or did not pass."},
        500: {"description": "Unexpected server error."},
    },
)
async def request_model_capability_restore_route(
    entry_id: str,
    request: ModelCapabilityRestoreIntentRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> GovernedActionResponse:
    return request_model_capability_restore(entry_id, request, authenticated_caller)


@router.post(
    "/catalogue/{entry_id}/capability-restore-approvals",
    response_model=ModelCapabilityRestoreApprovalResponse,
    operation_id="approveModelCapabilityRestore",
    summary="Approve and execute a pending capability restore",
    description=(
        "Step two of governed capability restore (issue #245, slice 2): a verified credential "
        "DISTINCT from the requester's approves the exact pending action hash, which clears "
        "the degradation and records the full request-approval-execution evidence chain with "
        "the cleared degradation pinned in the payload. A change to the degradation since the "
        "request refuses the stale approval."
    ),
    responses={
        200: {"description": "Capability restored under governed approval."},
        403: {
            "description": "Caller is not authorized, carries no verified credential, or is "
            "the same credential that requested the action."
        },
        404: {"description": "No entry or no pending action exists for the given id."},
        409: {
            "description": "The durable catalogue store is not configured, the action hash "
            "does not match, or the degradation changed since the request."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def approve_model_capability_restore_route(
    entry_id: str,
    request: ModelCapabilityRestoreApprovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> ModelCapabilityRestoreApprovalResponse:
    return approve_model_capability_restore(entry_id, request, authenticated_caller)
