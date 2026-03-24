from __future__ import annotations

from fastapi import APIRouter

from app.contracts.observability import (
    DomainIncidentSummaryResponse,
    ObservabilityIncidentSummaryResponse,
    ObservabilityRuntimeStatusResponse,
)
from app.services.observability_domain_summaries import (
    build_async_observability_bundle,
    build_evaluation_observability_bundle,
    build_prompt_observability_bundle,
    build_provider_observability_bundle,
    build_retrieval_observability_bundle,
    build_safety_observability_bundle,
)
from app.services.observability_incident_summary import build_observability_incident_summary
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


@router.get(
    "/incident-summary",
    response_model=ObservabilityIncidentSummaryResponse,
    operation_id="getObservabilityIncidentSummary",
    summary="Get observability incident summary",
    description=(
        "Returns bounded provider, retrieval, and async incident summaries grounded in current runtime state."
    ),
    responses={
        200: {"description": "Observability incident summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_observability_incident_summary_route() -> ObservabilityIncidentSummaryResponse:
    return build_observability_incident_summary()


@router.get(
    "/provider-summary",
    response_model=DomainIncidentSummaryResponse,
    operation_id="getProviderObservabilitySummary",
    summary="Get provider observability summary",
    description="Returns the bounded provider-domain observability and incident-evidence summary.",
    responses={
        200: {"description": "Provider observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_observability_summary_route() -> DomainIncidentSummaryResponse:
    return build_provider_observability_bundle().summary


@router.get(
    "/retrieval-summary",
    response_model=DomainIncidentSummaryResponse,
    operation_id="getRetrievalObservabilitySummary",
    summary="Get retrieval observability summary",
    description="Returns the bounded retrieval-domain observability and incident-evidence summary.",
    responses={
        200: {"description": "Retrieval observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_observability_summary_route() -> DomainIncidentSummaryResponse:
    return build_retrieval_observability_bundle().summary


@router.get(
    "/async-summary",
    response_model=DomainIncidentSummaryResponse,
    operation_id="getAsyncObservabilitySummary",
    summary="Get async observability summary",
    description="Returns the bounded async-domain observability and incident-evidence summary.",
    responses={
        200: {"description": "Async observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_observability_summary_route() -> DomainIncidentSummaryResponse:
    return build_async_observability_bundle().summary


@router.get(
    "/evaluation-summary",
    response_model=DomainIncidentSummaryResponse,
    operation_id="getEvaluationObservabilitySummary",
    summary="Get evaluation observability summary",
    description="Returns the bounded evaluation-domain observability and incident-evidence summary.",
    responses={
        200: {"description": "Evaluation observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_evaluation_observability_summary_route() -> DomainIncidentSummaryResponse:
    return build_evaluation_observability_bundle().summary


@router.get(
    "/prompt-summary",
    response_model=DomainIncidentSummaryResponse,
    operation_id="getPromptObservabilitySummary",
    summary="Get prompt observability summary",
    description="Returns the bounded prompt-domain observability and incident-evidence summary.",
    responses={
        200: {"description": "Prompt observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_prompt_observability_summary_route() -> DomainIncidentSummaryResponse:
    return build_prompt_observability_bundle().summary


@router.get(
    "/safety-summary",
    response_model=DomainIncidentSummaryResponse,
    operation_id="getSafetyObservabilitySummary",
    summary="Get safety observability summary",
    description="Returns the bounded safety-domain observability and incident-evidence summary.",
    responses={
        200: {"description": "Safety observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_safety_observability_summary_route() -> DomainIncidentSummaryResponse:
    return build_safety_observability_bundle().summary
