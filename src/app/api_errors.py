from __future__ import annotations

from http import HTTPStatus
from typing import Any, cast

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.structured_logging import log_event
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.contracts.api_errors import ProblemDetails

_DEFAULT_ERROR_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "LOTUS_AI_BAD_REQUEST",
    status.HTTP_403_FORBIDDEN: "LOTUS_AI_FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "LOTUS_AI_NOT_FOUND",
    status.HTTP_409_CONFLICT: "LOTUS_AI_CONFLICT",
    413: "LOTUS_AI_REQUEST_TOO_LARGE",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "LOTUS_AI_VALIDATION_FAILED",
    status.HTTP_429_TOO_MANY_REQUESTS: "LOTUS_AI_RATE_LIMITED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "LOTUS_AI_INTERNAL_ERROR",
    status.HTTP_503_SERVICE_UNAVAILABLE: "LOTUS_AI_SERVICE_UNAVAILABLE",
}

_DEFAULT_TITLES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "Bad request",
    status.HTTP_403_FORBIDDEN: "Forbidden",
    status.HTTP_404_NOT_FOUND: "Resource not found",
    status.HTTP_409_CONFLICT: "Request conflict",
    413: "Request body too large",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "Request validation failed",
    status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Unexpected server error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "Service unavailable",
}


def install_problem_detail_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
    app.add_exception_handler(RequestValidationError, cast(Any, validation_exception_handler))
    app.add_exception_handler(Exception, unexpected_exception_handler)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    status_code = int(exc.status_code)
    detail, metadata, explicit_code = _extract_detail(exc.detail)
    return build_problem_response(
        request=request,
        status_code=status_code,
        detail=detail,
        error_code=explicit_code or error_code_for_status(status_code, detail),
        metadata=metadata,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return build_problem_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Request validation failed.",
        error_code="LOTUS_AI_VALIDATION_FAILED",
        metadata={"validation_error_count": len(exc.errors())},
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return build_problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected lotus-ai server error.",
        error_code="LOTUS_AI_INTERNAL_ERROR",
    )


_logger = logging.getLogger("app.errors")


def build_problem_response(
    *,
    request: Request,
    status_code: int,
    detail: str,
    error_code: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> JSONResponse:
    code = error_code or error_code_for_status(status_code, detail)
    problem = ProblemDetails(
        type=f"https://lotus.ai/problems/{code.lower().replace('_', '-')}",
        title=_DEFAULT_TITLES.get(status_code, _title_for_status(status_code)),
        status=status_code,
        detail=_bounded_detail(detail, status_code=status_code),
        error_code=code,
        correlation_id=_correlation_id(request),
        metadata=metadata,
    )
    correlation_id = _correlation_id(request)
    route = request.scope.get("route")
    log_event(
        _logger,
        "problem_response",
        error_code=code,
        status_code=status_code,
        method=request.method,
        route=getattr(route, "path", request.url.path),
        caller_app=request.headers.get("X-Caller-App"),
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers={
            "X-Correlation-Id": correlation_id,
            "X-Service-Name": settings.service_name,
        },
    )


def error_code_for_status(status_code: int, detail: str | None = None) -> str:
    normalized_detail = (detail or "").lower()
    if status_code == status.HTTP_404_NOT_FOUND:
        if "workflow-pack run" in normalized_detail:
            return "LOTUS_AI_WORKFLOW_PACK_RUN_NOT_FOUND"
        if "workflow-pack" in normalized_detail:
            return "LOTUS_AI_WORKFLOW_PACK_NOT_FOUND"
        if "audit record" in normalized_detail:
            return "LOTUS_AI_AUDIT_RECORD_NOT_FOUND"
        if "task_id" in normalized_detail or "task id" in normalized_detail:
            return "LOTUS_AI_TASK_NOT_FOUND"
    if status_code == status.HTTP_403_FORBIDDEN:
        if "origin" in normalized_detail:
            return "LOTUS_AI_CORS_ORIGIN_FORBIDDEN"
        return "LOTUS_AI_CALLER_FORBIDDEN"
    if status_code == 413:
        return "LOTUS_AI_REQUEST_TOO_LARGE"
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return "LOTUS_AI_QUEUE_CAPACITY_EXCEEDED"
    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        return "LOTUS_AI_RUNTIME_STORE_UNAVAILABLE"
    return _DEFAULT_ERROR_CODES.get(status_code, "LOTUS_AI_HTTP_ERROR")


def _extract_detail(detail: Any) -> tuple[str, dict[str, Any] | None, str | None]:
    if isinstance(detail, dict):
        raw_detail = detail.get("detail") or detail.get("message") or "Request failed."
        metadata = detail.get("metadata")
        explicit_code = detail.get("error_code")
        return (
            str(raw_detail),
            metadata if isinstance(metadata, dict) else None,
            str(explicit_code) if explicit_code else None,
        )
    return str(detail) if detail else "Request failed.", None, None


def _bounded_detail(detail: str, *, status_code: int) -> str:
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            return detail[:300]
        return "Unexpected lotus-ai server error."
    return detail[:300]


def _correlation_id(request: Request) -> str:
    state_value = getattr(request.state, "correlation_id", None)
    if isinstance(state_value, str) and state_value:
        return state_value
    header_value = request.headers.get("X-Correlation-Id")
    if header_value:
        return header_value
    return "unavailable"


def _title_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP error"
