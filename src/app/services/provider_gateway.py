from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.providers import (
    ProviderExecutionMode,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.providers.registry import resolve_text_generation_adapter
from app.services.provider_policy import require_supported_text_generation_mode
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_quota_policy import enforce_provider_quota


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    mode = require_supported_text_generation_mode()
    live_execution_state = build_provider_live_execution_state(task_id=request.task_id)
    if mode == ProviderExecutionMode.OPENAI and not live_execution_state.live_execution_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED.value}: "
                f"{live_execution_state.blocking_reason}"
            ),
        )
    if mode == ProviderExecutionMode.OPENAI:
        try:
            enforce_provider_quota(request)
        except ProviderExecutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{exc.category.value}: {exc.message}",
            ) from exc
    adapter = resolve_text_generation_adapter(mode)
    try:
        return adapter.execute(request)
    except ProviderExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{exc.category.value}: {exc.message}",
        ) from exc
