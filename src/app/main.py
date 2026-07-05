from __future__ import annotations

from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, Response, status
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator import routing as prometheus_routing
from starlette.routing import Match, Mount, Route

from app.api_errors import install_problem_detail_handlers
from app.config import settings
from app.contracts.api_errors import COMMON_PROBLEM_RESPONSES, ProblemDetails
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.http_boundary import HttpBoundaryMiddleware
from app.routers.access_control import router as access_control_router
from app.routers.artifacts import router as artifacts_router
from app.routers.async_runtime import router as async_runtime_router
from app.routers.audit import router as audit_router
from app.routers.capabilities import router as capabilities_router
from app.routers.capability_packs import router as capability_packs_router
from app.routers.evals import router as evals_router
from app.routers.observability import router as observability_router
from app.routers.platform import router as platform_router
from app.routers.prompts import router as prompts_router
from app.routers.providers import router as providers_router
from app.routers.retrieval import router as retrieval_router
from app.routers.safety import router as safety_router
from app.routers.tasks import router as tasks_router
from app.routers.task_runtime import router as task_runtime_router
from app.routers.use_cases import router as use_cases_router
from app.routers.workflow_packs import router as workflow_packs_router
from app.services.startup_policy import apply_startup_readiness_policy

SERVICE_NAME = settings.service_name
SERVICE_VERSION = settings.service_version
ROUNDING_POLICY_VERSION = "v1"
_PROMETHEUS_ROUTING_PATCHED = False


def _install_fastapi_included_router_prometheus_patch() -> None:
    global _PROMETHEUS_ROUTING_PATCHED
    if _PROMETHEUS_ROUTING_PATCHED:
        return
    prometheus_routing._get_route_name = _get_prometheus_route_name
    _PROMETHEUS_ROUTING_PATCHED = True


def _get_prometheus_route_name(
    scope: MutableMapping[str, Any],
    routes: list[Route],
    route_name: str | None = None,
) -> str | None:
    """Resolve route names across Starlette routes and FastAPI deferred routers."""

    for route in routes:
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            matched_route = _resolve_effective_route(route, scope)
            route_path = getattr(matched_route, "path", None)
            if not isinstance(route_path, str):
                return route_name

            child_scope = {**scope, **child_scope}
            route_name = route_path
            if isinstance(matched_route, Mount) and matched_route.routes:
                child_route_name = _get_prometheus_route_name(
                    child_scope, cast(list[Route], matched_route.routes), route_name
                )
                if child_route_name is None:
                    route_name = None
                else:
                    route_name += child_route_name
            return route_name
        if match == Match.PARTIAL and route_name is None:
            route_path = getattr(route, "path", None)
            if isinstance(route_path, str):
                route_name = route_path
    return None


def _resolve_effective_route(route: Route, scope: MutableMapping[str, Any]) -> Any:
    match_method = getattr(route, "_match", None)
    if not callable(match_method):
        return route

    try:
        _match, _child_scope, matched_route, effective_context = match_method(scope)
    except Exception:
        return route
    if matched_route is not None:
        return matched_route
    starlette_route = getattr(effective_context, "starlette_route", None)
    return starlette_route or route


def _install_problem_details_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        spec = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schemas = spec.setdefault("components", {}).setdefault("schemas", {})
        schemas["ProblemDetails"] = ProblemDetails.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        problem_content = {
            "schema": {"$ref": "#/components/schemas/ProblemDetails"},
            "example": {
                "type": "https://lotus.ai/problems/validation-failed",
                "title": "Request validation failed",
                "status": 422,
                "detail": "Request validation failed.",
                "error_code": "LOTUS_AI_VALIDATION_FAILED",
                "correlation_id": "corr-example",
                "metadata": {"validation_error_count": 1},
            },
        }
        for methods in spec.get("paths", {}).values():
            for operation in methods.values():
                responses = operation.get("responses", {})
                for code, response in responses.items():
                    if str(code).startswith(("4", "5")):
                        response.setdefault("content", {})["application/problem+json"] = (
                            problem_content
                        )
        app.openapi_schema = spec
        return spec

    app.openapi = custom_openapi  # type: ignore[method-assign]


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
    responses=COMMON_PROBLEM_RESPONSES,
)
install_problem_detail_handlers(app)
app.add_middleware(HttpBoundaryMiddleware)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
_install_fastapi_included_router_prometheus_patch()
Instrumentator().instrument(app).expose(app)
app.include_router(platform_router)
app.include_router(artifacts_router)
app.include_router(observability_router)
app.include_router(access_control_router)
app.include_router(async_runtime_router)
app.include_router(capabilities_router)
app.include_router(capability_packs_router)
app.include_router(evals_router)
app.include_router(providers_router)
app.include_router(prompts_router)
app.include_router(retrieval_router)
app.include_router(safety_router)
app.include_router(task_runtime_router)
app.include_router(use_cases_router)
app.include_router(workflow_packs_router)
app.include_router(tasks_router)
app.include_router(audit_router)
_install_problem_details_openapi(app)


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
        "workflowPackRegistryStoreMode": settings.workflow_pack_registry_store_mode,
        "artifactStoreMode": settings.artifact_store_mode,
        "artifactObjectStoreMode": settings.artifact_object_store_mode,
        "auditStoreMode": settings.audit_store_mode,
        "retrievalStoreMode": settings.retrieval_store_mode,
        "workflowPackRunStoreMode": settings.workflow_pack_run_store_mode,
        "workflowPackTaskFlowStoreMode": settings.workflow_pack_task_flow_store_mode,
        "workflowPackQueueEventStoreMode": settings.workflow_pack_queue_event_store_mode,
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
        "workflowPackRegistryStoreMode": settings.workflow_pack_registry_store_mode,
        "artifactStoreMode": settings.artifact_store_mode,
        "artifactObjectStoreMode": settings.artifact_object_store_mode,
        "auditStoreMode": settings.audit_store_mode,
        "retrievalStoreMode": settings.retrieval_store_mode,
        "workflowPackRunStoreMode": settings.workflow_pack_run_store_mode,
        "workflowPackTaskFlowStoreMode": settings.workflow_pack_task_flow_store_mode,
        "workflowPackQueueEventStoreMode": settings.workflow_pack_queue_event_store_mode,
        "startupReadinessPolicy": settings.startup_readiness_policy,
        "readinessProbePolicy": settings.readiness_probe_policy,
        "capabilityAreas": [
            "llm_gateway",
            "async_runtime",
            "artifacts",
            "provider_catalog",
            "capability_packs",
            "workflow_packs",
            "workflow_pack_runs",
            "workflow_pack_task_flows",
            "workflow_pack_queue_events",
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
