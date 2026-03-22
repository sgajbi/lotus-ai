from __future__ import annotations

from fastapi import APIRouter

from app.contracts.async_runtime import (
    AsyncJobCatalogResponse,
    AsyncJobDetailResponse,
    AsyncJobSubmissionRequest,
    AsyncJobSubmissionResponse,
    AsyncQueueBackendCatalogResponse,
    AsyncRuntimeStatusResponse,
    AsyncWorkerExecutionCatalogResponse,
)
from app.services.async_job_service import build_async_job_catalog, build_async_job_detail
from app.services.async_queue_backend_service import build_async_queue_backend_catalog
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
        "Returns the current queue and worker posture for lotus-ai async execution, including "
        "known async job types and whether live background execution is active."
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
        "current foundation default and documented future backend options."
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
        "current foundation default and documented future worker rollout options."
    ),
    responses={
        200: {"description": "Async worker execution catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_worker_execution_catalog_route() -> AsyncWorkerExecutionCatalogResponse:
    return build_async_worker_execution_catalog()


@router.get(
    "/jobs",
    response_model=AsyncJobCatalogResponse,
    operation_id="getAsyncJobCatalog",
    summary="Get lotus-ai async job artifact catalog",
    description=(
        "Returns read-only seeded async job artifacts so the future worker path is inspectable "
        "before live queue execution is enabled."
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
        "Returns detail for a specific async job artifact, including current lifecycle state and "
        "planned execution path."
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
        "Validates a future async job submission against the current async runtime posture. "
        "During foundation phase, supported job types return an explicit rejected response so "
        "callers can integrate against the contract before live queue execution is enabled."
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
