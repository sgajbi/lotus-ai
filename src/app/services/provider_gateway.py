from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.base import ProviderExecutionError
from app.providers.registry import resolve_text_generation_adapter
from app.services.provider_policy import require_supported_text_generation_mode


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    mode = require_supported_text_generation_mode()
    adapter = resolve_text_generation_adapter(mode)
    try:
        return adapter.execute(request)
    except ProviderExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{exc.category.value}: {exc.message}",
        ) from exc
