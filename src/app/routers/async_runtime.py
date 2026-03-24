from __future__ import annotations

from fastapi import APIRouter

from app.contracts.async_runtime import (
    AsyncActivationReadinessResponse,
    AsyncControlActionRequest,
    AsyncControlActionResponse,
    AsyncControlHistoryResponse,
    AsyncGovernanceStatusResponse,
    AsyncJobCatalogResponse,
    AsyncJobDetailResponse,
    AsyncJobSubmissionRequest,
    AsyncJobSubmissionResponse,
    AsyncQueueBackendCatalogResponse,
    AsyncRunbookReadinessResponse,
    AsyncRuntimeStatusResponse,
    AsyncWorkerExecutionCatalogResponse,
)
from app.services.async_activation_readiness_service import build_async_activation_readiness
from app.services.async_runtime_control import (
    apply_async_control_action,
    build_async_control_history,
)
from app.services.async_governance_status_service import build_async_governance_status
from app.services.async_job_service import build_async_job_catalog, build_async_job_detail
from app.services.async_queue_backend_service import build_async_queue_backend_catalog
from app.services.async_runbook_readiness_service import build_async_runbook_readiness
from app.services.async_submission_service import submit_async_job
from app.services.async_runtime_status import build_async_runtime_status
from app.services.async_worker_execution_service import build_async_worker_execution_catalog

router = APIRouter(prefix="/platform/async", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=AsyncRuntimeStatusResponse,
    operation_id="getAsyncRuntimeStatus",
    summary="Get lotus-ai async runtime status",
    description=(
        "Returns the current async cutover state, queue posture, and worker posture for lotus-ai "
        "async execution, including whether managed queue delivery is disabled, running in shadow "
        "mode, or serving a dedicated worker fleet."
    ),
    responses={
        200: {"description": "Async runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_runtime_status_route() -> AsyncRuntimeStatusResponse:
    return build_async_runtime_status()


@router.get(
    "/queue-backends",
    response_model=AsyncQueueBackendCatalogResponse,
    operation_id="getAsyncQueueBackendCatalog",
    summary="Get lotus-ai async queue backend catalog",
    description=(
        "Returns the governed queue backend strategies recognized by lotus-ai, including the "
        "current managed-queue posture and documented future worker-scalable backend options."
    ),
    responses={
        200: {"description": "Async queue backend catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_queue_backend_catalog_route() -> AsyncQueueBackendCatalogResponse:
    return build_async_queue_backend_catalog()


@router.get(
    "/worker-executions",
    response_model=AsyncWorkerExecutionCatalogResponse,
    operation_id="getAsyncWorkerExecutionCatalog",
    summary="Get lotus-ai async worker execution catalog",
    description=(
        "Returns the governed worker execution strategies recognized by lotus-ai, including the "
        "current in-process default and documented future dedicated worker rollout options."
    ),
    responses={
        200: {"description": "Async worker execution catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_worker_execution_catalog_route() -> AsyncWorkerExecutionCatalogResponse:
    return build_async_worker_execution_catalog()


@router.get(
    "/activation-readiness",
    response_model=AsyncActivationReadinessResponse,
    operation_id="getAsyncActivationReadiness",
    summary="Get lotus-ai async activation readiness",
    description=(
        "Returns whether lotus-ai async execution is currently ready for live activation, along "
        "with the blocking findings and governed activation path beyond the current cutover posture."
    ),
    responses={
        200: {"description": "Async activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_activation_readiness_route() -> AsyncActivationReadinessResponse:
    return build_async_activation_readiness()


@router.get(
    "/runbook-readiness",
    response_model=AsyncRunbookReadinessResponse,
    operation_id="getAsyncRunbookReadiness",
    summary="Get lotus-ai async runbook readiness",
    description=(
        "Returns the operational runbook readiness required before lotus-ai async execution can "
        "be activated in a governed environment."
    ),
    responses={
        200: {"description": "Async runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_runbook_readiness_route() -> AsyncRunbookReadinessResponse:
    return build_async_runbook_readiness()


@router.get(
    "/governance-status",
    response_model=AsyncGovernanceStatusResponse,
    operation_id="getAsyncGovernanceStatus",
    summary="Get lotus-ai async governance status",
    description=(
        "Returns the combined technical and operational governance posture for lotus-ai async "
        "execution so rollout reviewers can assess activation readiness in one view."
    ),
    responses={
        200: {"description": "Async governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_governance_status_route() -> AsyncGovernanceStatusResponse:
    return build_async_governance_status()


@router.get(
    "/control-plane-actions",
    response_model=AsyncControlHistoryResponse,
    operation_id="getAsyncControlHistory",
    summary="Get lotus-ai async control-plane history",
    description=(
        "Returns the recent governed async retry, replay, requeue, and abandon actions recorded "
        "for runtime-backed async jobs."
    ),
    responses={
        200: {"description": "Async control-plane history returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_control_history_route() -> AsyncControlHistoryResponse:
    return build_async_control_history()


@router.post(
    "/control-plane-actions/apply",
    response_model=AsyncControlActionResponse,
    operation_id="applyAsyncControlAction",
    summary="Apply a lotus-ai async control-plane action",
    description=(
        "Applies one governed async retry, replay, requeue, or abandon action and records "
        "operator reason plus approval metadata for later review."
    ),
    responses={
        200: {"description": "Async control-plane action applied successfully."},
        404: {"description": "Async runtime job not found."},
        409: {"description": "Async control action conflicts with the current job state."},
        422: {"description": "Invalid async control action request."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_async_control_action_route(
    request: AsyncControlActionRequest,
) -> AsyncControlActionResponse:
    return apply_async_control_action(request)


@router.get(
    "/jobs",
    response_model=AsyncJobCatalogResponse,
    operation_id="getAsyncJobCatalog",
    summary="Get lotus-ai async job artifact catalog",
    description=(
        "Returns the current async job catalog, combining runtime-backed durable submissions with "
        "staged artifact records that still document future worker-enabled paths."
    ),
    responses={
        200: {"description": "Async job artifact catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_job_catalog_route() -> AsyncJobCatalogResponse:
    return build_async_job_catalog()


@router.get(
    "/jobs/{job_id}",
    response_model=AsyncJobDetailResponse,
    operation_id="getAsyncJobDetail",
    summary="Get lotus-ai async job artifact detail",
    description=(
        "Returns detail for a specific async job record, whether it comes from durable runtime "
        "state or a staged artifact describing a future worker-enabled path."
    ),
    responses={
        200: {"description": "Async job artifact detail returned successfully."},
        404: {"description": "Async job artifact not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_job_detail_route(job_id: str) -> AsyncJobDetailResponse:
    return build_async_job_detail(job_id=job_id)


@router.post(
    "/jobs/submit",
    response_model=AsyncJobSubmissionResponse,
    operation_id="submitAsyncJob",
    summary="Submit a lotus-ai async job request",
    description=(
        "Validates an async job submission against the current async runtime posture. Allowlisted "
        "job types are durably recorded in authoritative runtime state, staged-only job "
        "types return an explicit rejected response, and duplicate active retrieval-index "
        "submissions are rejected with the owning runtime job id."
    ),
    responses={
        200: {"description": "Async job submission evaluated successfully."},
        404: {"description": "Unknown async job type."},
        500: {"description": "Unexpected server error."},
    },
)
async def submit_async_job_route(
    request: AsyncJobSubmissionRequest,
) -> AsyncJobSubmissionResponse:
    return submit_async_job(request)
