from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.services.structured_logging import bind_correlation_context, log_event

_logger = logging.getLogger("app.http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        provided = request.headers.get("X-Correlation-Id")
        correlation_id = provided or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        bind_correlation_context(
            correlation_id=correlation_id,
            source="provided" if provided else "generated",
        )
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Correlation-Id"] = correlation_id
        response.headers["X-Service-Name"] = self._service_name
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.3f}"
        route = request.scope.get("route")
        log_event(
            _logger,
            "http_request",
            method=request.method,
            route=getattr(route, "path", request.url.path),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 3),
            caller_app=request.headers.get("X-Caller-App"),
        )
        return response
