from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts.prompts import (
    PromptPromotionApprovalRequest,
    PromptPromotionApprovalResponse,
    PromptPromotionIntentRequest,
    PromptActivationReadinessResponse,
    PromptControlActionRequest,
    PromptControlActionResponse,
    PromptControlHistoryResponse,
    PromptDescriptor,
    PromptEvidenceReadinessResponse,
    PromptGovernanceStatusResponse,
    PromptGovernanceStatusSummaryResponse,
    PromptRunbookReadinessResponse,
    PromptRuntimeStatusResponse,
)
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.prompt_activation_readiness import build_prompt_activation_readiness
from app.services.prompt_evidence_readiness import build_prompt_evidence_readiness
from app.services.prompt_governance import build_prompt_governance_status
from app.services.prompt_governance_status import build_prompt_governance_status_summary
from app.contracts.governed_actions import GovernedActionResponse
from app.services.prompt_rollout_control import (
    approve_prompt_promotion,
    request_prompt_promotion,
    apply_prompt_control_action,
    build_prompt_control_history,
)
from app.services.prompt_registry import get_prompt_or_raise, list_registered_prompts
from app.services.readiness_catalog import build_prompt_runbook_readiness
from app.services.prompt_status import build_prompt_runtime_status

router = APIRouter(prefix="/platform/prompts", tags=["platform"])


@router.get(
    "",
    response_model=list[PromptDescriptor],
    operation_id="listPromptDefinitions",
    summary="List registered lotus-ai prompts",
    description=(
        "Returns the currently registered prompt definitions known to lotus-ai. "
        "This endpoint is intended for platform transparency and engineering inspection."
    ),
    responses={
        200: {"description": "Prompt registry returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_prompts_route() -> list[PromptDescriptor]:
    return list_registered_prompts()


@router.get(
    "/governance",
    response_model=PromptGovernanceStatusResponse,
    operation_id="getPromptGovernanceStatus",
    summary="Get lotus-ai prompt governance status",
    description=(
        "Returns the current prompt governance posture, including whether runtime mutation "
        "is allowed and how prompt promotion is managed in the current phase."
    ),
    responses={
        200: {"description": "Prompt governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_governance_route() -> PromptGovernanceStatusResponse:
    return build_prompt_governance_status()


@router.get(
    "/control-history",
    response_model=PromptControlHistoryResponse,
    operation_id="getPromptControlHistory",
    summary="Get lotus-ai prompt control history",
    description=(
        "Returns durable prompt promote and rollback history so operators can inspect "
        "reviewable rollout actions over time."
    ),
    responses={
        200: {"description": "Prompt control history returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_control_history_route(
    task_id: str | None = None,
    limit: int = Query(
        default=20,
        ge=1,
        le=200,
        description="Maximum number of newest prompt control events to return.",
    ),
) -> PromptControlHistoryResponse:
    return build_prompt_control_history(task_id=task_id, limit=limit)


@router.post(
    "/promote-requests",
    response_model=GovernedActionResponse,
    operation_id="requestPromptPromotion",
    summary="Request promotion of a candidate prompt",
    description=(
        "Step one of governed promotion (issue #157): validates the promotion is currently "
        "executable, then records a pending intent under the requester's verified credential "
        "and returns the action hash a distinct verified credential must approve. The active "
        "prompt is unchanged until the approval executes."
    ),
    responses={
        200: {"description": "Promotion intent recorded and pending approval."},
        403: {
            "description": "Caller is not authorized for prompt control, or carries no "
            "verified credential."
        },
        404: {"description": "Rollout state or candidate prompt version not found."},
        409: {"description": "The promotion is not currently executable."},
        500: {"description": "Unexpected server error."},
    },
)
async def request_prompt_promotion_route(
    request: PromptPromotionIntentRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> GovernedActionResponse:
    return request_prompt_promotion(request, authenticated_caller)


@router.post(
    "/promote-approvals",
    response_model=PromptPromotionApprovalResponse,
    operation_id="approvePromptPromotion",
    summary="Approve and execute a pending prompt promotion",
    description=(
        "Step two of governed promotion (issue #157): a verified credential DISTINCT from the "
        "requester's approves the exact pending action hash, which promotes the candidate and "
        "records the full request-approval-execution evidence chain."
    ),
    responses={
        200: {"description": "Candidate promoted under governed approval."},
        403: {
            "description": "Caller is not authorized, carries no verified credential, or is "
            "the same credential that requested the promotion."
        },
        404: {"description": "No rollout state or pending action exists."},
        409: {
            "description": "The action hash does not match, the rollout state changed since "
            "the request, or the action is not pending."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def approve_prompt_promotion_route(
    request: PromptPromotionApprovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> PromptPromotionApprovalResponse:
    return approve_prompt_promotion(request, authenticated_caller)


@router.post(
    "/control-actions",
    response_model=PromptControlActionResponse,
    operation_id="applyPromptControlAction",
    summary="Apply a governed lotus-ai prompt control action",
    description=(
        "Applies a bounded prompt promote or rollback action against durable rollout state. "
        "Prompt-body editing remains out of scope for this API."
    ),
    responses={
        200: {"description": "Prompt control action applied successfully."},
        404: {"description": "Prompt rollout state or candidate version not found."},
        409: {"description": "Prompt control action was rejected due to an invalid transition."},
        422: {"description": "Prompt control action payload was invalid for the requested action."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_prompt_control_action_route(
    request: PromptControlActionRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> PromptControlActionResponse:
    return apply_prompt_control_action(request, authenticated_caller)


@router.get(
    "/runtime-status",
    response_model=PromptRuntimeStatusResponse,
    operation_id="getPromptRuntimeStatus",
    summary="Get lotus-ai prompt runtime status",
    description=(
        "Returns the current prompt runtime selection posture, including which prompt versions "
        "are actively selected for each task in the current phase."
    ),
    responses={
        200: {"description": "Prompt runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_runtime_status_route() -> PromptRuntimeStatusResponse:
    return build_prompt_runtime_status()


@router.get(
    "/activation-readiness",
    response_model=PromptActivationReadinessResponse,
    operation_id="getPromptActivationReadiness",
    summary="Get lotus-ai prompt activation readiness",
    description=(
        "Returns whether lotus-ai prompt rollout is currently ready for a live activation change, "
        "along with the blocking findings and governed activation path for future rollout."
    ),
    responses={
        200: {"description": "Prompt activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_activation_readiness_route() -> PromptActivationReadinessResponse:
    return build_prompt_activation_readiness()


@router.get(
    "/runbook-readiness",
    response_model=PromptRunbookReadinessResponse,
    operation_id="getPromptRunbookReadiness",
    summary="Get lotus-ai prompt runbook readiness",
    description=(
        "Returns whether lotus-ai prompt rollout is currently supported by the required "
        "operational runbooks and support procedures for future live activation."
    ),
    responses={
        200: {"description": "Prompt runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_runbook_readiness_route() -> PromptRunbookReadinessResponse:
    return build_prompt_runbook_readiness()


@router.get(
    "/evidence-readiness",
    response_model=PromptEvidenceReadinessResponse,
    operation_id="getPromptEvidenceReadiness",
    summary="Get lotus-ai prompt evidence readiness",
    description=(
        "Returns whether lotus-ai prompt rollout is currently supported by the required "
        "evaluation, audit, and rollback evidence needed for future live activation."
    ),
    responses={
        200: {"description": "Prompt evidence readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_evidence_readiness_route() -> PromptEvidenceReadinessResponse:
    return build_prompt_evidence_readiness()


@router.get(
    "/governance-status",
    response_model=PromptGovernanceStatusSummaryResponse,
    operation_id="getPromptGovernanceSummary",
    summary="Get lotus-ai prompt governance status",
    description=(
        "Returns the combined prompt rollout governance posture, including technical activation "
        "readiness and operational runbook readiness for future live activation."
    ),
    responses={
        200: {"description": "Prompt governance summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_governance_summary_route() -> PromptGovernanceStatusSummaryResponse:
    return build_prompt_governance_status_summary()


@router.get(
    "/{task_id}",
    response_model=PromptDescriptor,
    operation_id="getPromptDefinition",
    summary="Get lotus-ai prompt definition",
    description="Returns the registered prompt definition associated with a task identifier.",
    responses={
        200: {"description": "Prompt definition returned successfully."},
        404: {"description": "Prompt definition not found for the given task id."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_route(task_id: str) -> PromptDescriptor:
    return get_prompt_or_raise(task_id)
