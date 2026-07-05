from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.api_errors import build_problem_response
from app.config import settings


@dataclass(frozen=True)
class HttpBoundaryPosture:
    allowed_hosts: tuple[str, ...]
    cors_allowed_origins: tuple[str, ...]
    cors_allowed_methods: tuple[str, ...]
    cors_allowed_headers: tuple[str, ...]
    cors_allow_credentials: bool
    secure_headers_enabled: bool
    hsts_enabled: bool
    hsts_max_age_seconds: int
    max_request_body_bytes: int


class HttpBoundaryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        posture = current_http_boundary_posture()
        host_failure = _validate_host(request, posture)
        if host_failure is not None:
            return _decorate_response(host_failure, request, posture)

        size_failure = _validate_request_size(request, posture)
        if size_failure is not None:
            return _decorate_response(size_failure, request, posture)

        preflight_response = _build_preflight_response(request, posture)
        if preflight_response is not None:
            return _decorate_response(preflight_response, request, posture)

        response = await call_next(request)
        return _decorate_response(response, request, posture)


def current_http_boundary_posture() -> HttpBoundaryPosture:
    return HttpBoundaryPosture(
        allowed_hosts=_parse_csv(settings.http_allowed_hosts),
        cors_allowed_origins=_parse_csv(settings.http_cors_allowed_origins),
        cors_allowed_methods=_parse_csv(settings.http_cors_allowed_methods),
        cors_allowed_headers=_parse_csv(settings.http_cors_allowed_headers),
        cors_allow_credentials=settings.http_cors_allow_credentials,
        secure_headers_enabled=settings.http_secure_headers_enabled,
        hsts_enabled=settings.http_hsts_enabled,
        hsts_max_age_seconds=settings.http_hsts_max_age_seconds,
        max_request_body_bytes=settings.http_max_request_body_bytes,
    )


def _validate_host(request: Request, posture: HttpBoundaryPosture) -> Response | None:
    if "*" in posture.allowed_hosts:
        return None
    host = (request.headers.get("host") or "").split(":", maxsplit=1)[0].lower()
    allowed = {entry.lower() for entry in posture.allowed_hosts}
    if host in allowed:
        return None
    return build_problem_response(
        request=request,
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Request host is not allowed by the lotus-ai HTTP boundary policy.",
        error_code="LOTUS_AI_HOST_NOT_ALLOWED",
        metadata={"boundary_control": "trusted_host"},
    )


def _validate_request_size(request: Request, posture: HttpBoundaryPosture) -> Response | None:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return None
    try:
        body_size = int(content_length)
    except ValueError:
        return build_problem_response(
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request content length is invalid.",
            error_code="LOTUS_AI_INVALID_CONTENT_LENGTH",
            metadata={"boundary_control": "request_size"},
        )
    if body_size <= posture.max_request_body_bytes:
        return None
    return build_problem_response(
        request=request,
        status_code=413,
        detail="Request body exceeds the configured lotus-ai maximum size.",
        error_code="LOTUS_AI_REQUEST_TOO_LARGE",
        metadata={
            "boundary_control": "request_size",
            "max_request_body_bytes": posture.max_request_body_bytes,
        },
    )


def _build_preflight_response(request: Request, posture: HttpBoundaryPosture) -> Response | None:
    if (
        request.method.upper() != "OPTIONS"
        or "access-control-request-method" not in request.headers
    ):
        return None
    origin = request.headers.get("origin")
    if not _is_allowed_origin(origin, posture):
        return build_problem_response(
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CORS origin is not allowed by the lotus-ai HTTP boundary policy.",
            error_code="LOTUS_AI_CORS_ORIGIN_FORBIDDEN",
            metadata={"boundary_control": "cors"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _decorate_response(
    response: Response, request: Request, posture: HttpBoundaryPosture
) -> Response:
    if posture.secure_headers_enabled:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), geolocation=(), microphone=()"
        )
        if posture.hsts_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={posture.hsts_max_age_seconds}; includeSubDomains",
            )
    _apply_cors_headers(response, request, posture)
    return response


def _apply_cors_headers(response: Response, request: Request, posture: HttpBoundaryPosture) -> None:
    origin = request.headers.get("origin")
    if not _is_allowed_origin(origin, posture):
        return
    response.headers["Access-Control-Allow-Origin"] = (
        "*" if "*" in posture.cors_allowed_origins else origin or "*"
    )
    response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = ", ".join(posture.cors_allowed_methods)
    response.headers["Access-Control-Allow-Headers"] = ", ".join(posture.cors_allowed_headers)
    if posture.cors_allow_credentials:
        response.headers["Access-Control-Allow-Credentials"] = "true"


def _is_allowed_origin(origin: str | None, posture: HttpBoundaryPosture) -> bool:
    if origin is None:
        return False
    if "*" in posture.cors_allowed_origins:
        return True
    return origin in posture.cors_allowed_origins


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())
