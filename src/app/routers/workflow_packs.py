from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.contracts.workflow_packs import (
    WorkflowPackControlActionRequest,
    WorkflowPackControlActionResponse,
    WorkflowPackControlHistoryResponse,
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackEligibilityEvaluationResponse,
    WorkflowPackExecutionRequest,
    WorkflowPackExecutionResponse,
    WorkflowPackRegistrationDetailResponse,
    WorkflowPackRegistryCatalogResponse,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
    WorkflowPackRunConsumerViewResponse,
    WorkflowPackRunDetailResponse,
    WorkflowPackRunOperatorProfileResponse,
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionResponse,
)
from app.services.workflow_pack_run_consumer_view import build_workflow_pack_run_consumer_view
from app.services.workflow_pack_run_operator_profile import build_workflow_pack_run_operator_profile
from app.services.workflow_pack_control import (
    apply_workflow_pack_control_action,
    build_workflow_pack_control_history,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
from app.services.workflow_pack_execution import execute_workflow_pack
from app.services.workflow_pack_run_ledger import (
    build_workflow_pack_run_catalog,
    build_workflow_pack_run_detail,
)
from app.services.workflow_pack_run_review import apply_workflow_pack_run_review_action
from app.services.workflow_pack_registry import (
    build_workflow_pack_registration_detail,
    build_workflow_pack_registry_catalog,
)

router = APIRouter(tags=["platform"])


@router.get(
    "/platform/workflow-packs/registry",
    response_model=WorkflowPackRegistryCatalogResponse,
    operation_id="getWorkflowPackRegistryCatalog",
    summary="Get lotus-ai workflow-pack registry catalog",
    description=(
        "Returns the current workflow-pack registry and validation posture exposed by lotus-ai. "
        "This registry is the control-plane record for known workflow-pack versions, not the editable home of workflow logic."
    ),
    responses={
        200: {"description": "Workflow-pack registry catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_registry_catalog() -> WorkflowPackRegistryCatalogResponse:
    return build_workflow_pack_registry_catalog()


@router.get(
    "/platform/workflow-packs/registry/{pack_id}/{version}",
    response_model=WorkflowPackRegistrationDetailResponse,
    operation_id="getWorkflowPackRegistrationDetail",
    summary="Get lotus-ai workflow-pack registration detail",
    description=(
        "Returns one workflow-pack registration record, including bounded ownership, scope, and registration-validation posture."
    ),
    responses={
        200: {"description": "Workflow-pack registration detail returned successfully."},
        404: {"description": "Workflow-pack registration not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_registration_detail(
    pack_id: str,
    version: str,
) -> WorkflowPackRegistrationDetailResponse:
    try:
        return build_workflow_pack_registration_detail(pack_id=pack_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/eligibility/evaluate",
    response_model=WorkflowPackEligibilityEvaluationResponse,
    operation_id="evaluateWorkflowPackEligibility",
    summary="Evaluate lotus-ai workflow-pack eligibility",
    description=(
        "Evaluates whether one workflow-pack version is currently eligible for execution under the declared caller, environment, and workflow-scope posture."
    ),
    responses={
        200: {"description": "Workflow-pack eligibility evaluated successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def evaluate_workflow_pack_eligibility_route(
    request: WorkflowPackEligibilityEvaluationRequest,
) -> WorkflowPackEligibilityEvaluationResponse:
    return evaluate_workflow_pack_eligibility(request)


@router.post(
    "/platform/workflow-packs/execute",
    response_model=WorkflowPackExecutionResponse,
    operation_id="executeWorkflowPack",
    summary="Execute a lotus-ai workflow pack through the explicit workflow-pack seam",
    description=(
        "Evaluates workflow-pack eligibility, runs the bounded lotus-ai task pipeline for the "
        "declared pack binding, and records an explicit workflow-pack run."
    ),
    responses={
        200: {"description": "Workflow-pack executed successfully."},
        403: {"description": "Workflow-pack execution is not currently allowed."},
        404: {"description": "Workflow-pack registration not found."},
        409: {"description": "Workflow-pack execution binding is not available for this request."},
        422: {"description": "Workflow-pack execution payload is invalid for the requested pack."},
        500: {"description": "Unexpected server error."},
    },
)
async def execute_workflow_pack_route(
    request: WorkflowPackExecutionRequest,
) -> WorkflowPackExecutionResponse:
    return execute_workflow_pack(request)


@router.get(
    "/platform/workflow-packs/control-history",
    response_model=WorkflowPackControlHistoryResponse,
    operation_id="getWorkflowPackControlHistory",
    summary="Get lotus-ai workflow-pack control history",
    description=(
        "Returns recent workflow-pack pause, resume, deprecate, and retire actions recorded by the workflow-pack control plane."
    ),
    responses={
        200: {"description": "Workflow-pack control history returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_control_history_route(
    pack_id: str | None = None,
    version: str | None = None,
    limit: int = 20,
) -> WorkflowPackControlHistoryResponse:
    return build_workflow_pack_control_history(pack_id=pack_id, version=version, limit=limit)


@router.get(
    "/platform/workflow-packs/runs",
    response_model=WorkflowPackRunCatalogResponse,
    operation_id="getWorkflowPackRunCatalog",
    summary="Get lotus-ai workflow-pack run catalog",
    description=(
        "Returns the current workflow-pack run-ledger catalog, including runtime-state and "
        "review-state posture for recorded workflow-pack executions."
    ),
    responses={
        200: {"description": "Workflow-pack run catalog returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_catalog_route() -> WorkflowPackRunCatalogResponse:
    return build_workflow_pack_run_catalog()


@router.get(
    "/platform/workflow-packs/runs/{run_id}",
    response_model=WorkflowPackRunDetailResponse,
    operation_id="getWorkflowPackRunDetail",
    summary="Get lotus-ai workflow-pack run detail",
    description=(
        "Returns detailed workflow-pack run-ledger state, including recorded run history events."
    ),
    responses={
        200: {"description": "Workflow-pack run detail returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_detail_route(run_id: str) -> WorkflowPackRunDetailResponse:
    return build_workflow_pack_run_detail(run_id=run_id)


@router.get(
    "/platform/workflow-packs/runs/{run_id}/consumer-view",
    response_model=WorkflowPackRunConsumerViewResponse,
    operation_id="getWorkflowPackRunConsumerView",
    summary="Get lotus-ai workflow-pack run consumer view",
    description=(
        "Returns a bounded consumer-facing contract for one workflow-pack run, grouping runtime, "
        "review, lineage, and provenance posture without transferring downstream workflow authority."
    ),
    responses={
        200: {"description": "Workflow-pack run consumer view returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_consumer_view_route(
    run_id: str,
) -> WorkflowPackRunConsumerViewResponse:
    return build_workflow_pack_run_consumer_view(run_id=run_id)


@router.get(
    "/platform/workflow-packs/runs/{run_id}/operator-profile",
    response_model=WorkflowPackRunOperatorProfileResponse,
    operation_id="getWorkflowPackRunOperatorProfile",
    summary="Get lotus-ai workflow-pack run operator profile",
    description=(
        "Returns one operator-facing workflow-pack run supportability profile, including runtime, "
        "review, supersession, artifact, and evidence posture for diagnosis."
    ),
    responses={
        200: {"description": "Workflow-pack run operator profile returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_operator_profile_route(
    run_id: str,
) -> WorkflowPackRunOperatorProfileResponse:
    return build_workflow_pack_run_operator_profile(run_id=run_id)


@router.post(
    "/platform/workflow-packs/runs/{run_id}/review-actions",
    response_model=WorkflowPackRunReviewActionResponse,
    operation_id="applyWorkflowPackRunReviewAction",
    summary="Apply a lotus-ai workflow-pack run review action",
    description=(
        "Records one bounded workflow-pack review-state action while preserving the separation "
        "between runtime execution posture and consequence-bearing downstream workflow authority."
    ),
    responses={
        200: {"description": "Workflow-pack run review action applied successfully."},
        403: {
            "description": "Caller is not currently authorized for workflow-pack review-state actions."
        },
        404: {"description": "Workflow-pack run or replacement run not found."},
        409: {
            "description": "Workflow-pack review-state action conflicts with the current run posture."
        },
        422: {"description": "Invalid review-state action payload."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_workflow_pack_run_review_action_route(
    run_id: str,
    request: WorkflowPackRunReviewActionRequest,
) -> WorkflowPackRunReviewActionResponse:
    return apply_workflow_pack_run_review_action(run_id=run_id, request=request)


@router.post(
    "/platform/workflow-packs/control-actions",
    response_model=WorkflowPackControlActionResponse,
    operation_id="applyWorkflowPackControlAction",
    summary="Apply a lotus-ai workflow-pack control action",
    description=(
        "Applies one bounded workflow-pack pause, resume, deprecate, or retire action and records the resulting control-plane event."
    ),
    responses={
        200: {"description": "Workflow-pack control action applied successfully."},
        403: {
            "description": "Caller is not currently authorized for workflow-pack control actions."
        },
        404: {"description": "Workflow-pack registration not found."},
        409: {
            "description": "Workflow-pack control action conflicts with the current registration state."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def apply_workflow_pack_control_action_route(
    request: WorkflowPackControlActionRequest,
) -> WorkflowPackControlActionResponse:
    return apply_workflow_pack_control_action(request)
