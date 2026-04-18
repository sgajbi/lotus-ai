from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.contracts.workflow_packs import (
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackEligibilityEvaluationResponse,
    WorkflowPackRegistrationDetailResponse,
    WorkflowPackRegistryCatalogResponse,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
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
