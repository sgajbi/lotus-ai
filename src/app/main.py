from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routers.access_control import router as access_control_router
from app.routers.async_runtime import router as async_runtime_router
from app.routers.audit import router as audit_router
from app.routers.capabilities import router as capabilities_router
from app.routers.evals import router as evals_router
from app.routers.platform import router as platform_router
from app.routers.prompts import router as prompts_router
from app.routers.providers import router as providers_router
from app.routers.retrieval import router as retrieval_router
from app.routers.safety import router as safety_router
from app.routers.tasks import router as tasks_router
from app.routers.task_runtime import router as task_runtime_router
from app.services.startup_policy import apply_startup_readiness_policy

SERVICE_NAME = settings.service_name
SERVICE_VERSION = settings.service_version
ROUNDING_POLICY_VERSION = "v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    evaluation = apply_startup_readiness_policy()
    app.state.startup_readiness_blocking = evaluation.blocking
    app.state.startup_readiness_findings = evaluation.findings
    yield


app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    description=(
        "Shared AI platform service for Lotus applications. "
        "This service owns reusable AI infrastructure and governed task execution, "
        "not domain business truth."
    ),
    lifespan=lifespan,
)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
Instrumentator().instrument(app).expose(app)
app.include_router(platform_router)
app.include_router(access_control_router)
app.include_router(async_runtime_router)
app.include_router(capabilities_router)
app.include_router(evals_router)
app.include_router(providers_router)
app.include_router(prompts_router)
app.include_router(retrieval_router)
app.include_router(safety_router)
app.include_router(task_runtime_router)
app.include_router(tasks_router)
app.include_router(audit_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, str]:
    if bool(getattr(app.state, "is_draining", False)):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "draining"}
    findings = list(getattr(app.state, "startup_readiness_findings", []))
    if settings.readiness_probe_policy == "degrade" and findings:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded"}
    return {"status": "ready"}


@app.get(
    "/metadata",
    tags=["platform"],
    operation_id="getServiceMetadata",
    summary="Get lotus-ai service metadata",
    description=(
        "Returns core service metadata for lotus-ai, including service version and the "
        "current rounding policy version marker."
    ),
    responses={
        200: {"description": "Metadata returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def metadata() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "roundingPolicyVersion": ROUNDING_POLICY_VERSION,
        "promptStoreMode": settings.prompt_store_mode,
        "accessControlStoreMode": settings.access_control_store_mode,
        "auditStoreMode": settings.audit_store_mode,
        "retrievalStoreMode": settings.retrieval_store_mode,
        "startupReadinessPolicy": settings.startup_readiness_policy,
        "readinessProbePolicy": settings.readiness_probe_policy,
    }


@app.get(
    "/",
    tags=["platform"],
    operation_id="getServiceOverview",
    summary="Get lotus-ai service overview",
    description=(
        "Returns the current high-level lotus-ai service state, including delivery phase and "
        "major capability areas exposed by the platform."
    ),
    responses={
        200: {"description": "Overview returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def root() -> dict[str, object]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "phase": settings.delivery_phase,
        "providerMode": settings.provider_mode,
        "retrievalMode": settings.retrieval_mode,
        "embeddingProviderMode": settings.embedding_provider_mode,
        "safetyMode": settings.safety_mode,
        "promptStoreMode": settings.prompt_store_mode,
        "accessControlStoreMode": settings.access_control_store_mode,
        "auditStoreMode": settings.audit_store_mode,
        "retrievalStoreMode": settings.retrieval_store_mode,
        "startupReadinessPolicy": settings.startup_readiness_policy,
        "readinessProbePolicy": settings.readiness_probe_policy,
        "capabilityAreas": [
            "llm_gateway",
            "async_runtime",
            "provider_catalog",
            "prompt_registry",
            "access_control",
            "retrieval",
            "safety",
            "task_runtime",
            "evals",
            "task_apis",
            "platform_runtime_status",
        ],
    }
