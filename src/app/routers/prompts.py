from __future__ import annotations

from fastapi import APIRouter

from app.contracts.prompts import (
    PromptActivationReadinessResponse,
    PromptDescriptor,
    PromptGovernanceStatusResponse,
    PromptGovernanceStatusSummaryResponse,
    PromptRunbookReadinessResponse,
    PromptRuntimeStatusResponse,
)
from app.services.prompt_activation_readiness import build_prompt_activation_readiness
from app.services.prompt_governance import build_prompt_governance_status
from app.services.prompt_governance_status import build_prompt_governance_status_summary
from app.services.prompt_registry import get_prompt_or_raise, list_registered_prompts
from app.services.prompt_runbook_readiness import build_prompt_runbook_readiness
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
