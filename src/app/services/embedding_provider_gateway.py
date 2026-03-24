from __future__ import annotations

from app.contracts.providers import (
    EmbeddingExecutionRequest,
    EmbeddingExecutionResponse,
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.providers.registry import resolve_embedding_adapter
from app.services.embedding_live_execution_state import build_embedding_live_execution_state
from app.services.provider_policy import require_supported_embedding_mode


def execute_embedding_generation(request: EmbeddingExecutionRequest) -> EmbeddingExecutionResponse:
    mode = require_supported_embedding_mode()
    live_execution_state = build_embedding_live_execution_state()
    if mode == ProviderExecutionMode.ENABLED and not live_execution_state.live_execution_enabled:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
            message=live_execution_state.blocking_reason
            or "Live embedding execution is not currently enabled.",
        )
    adapter = resolve_embedding_adapter(mode)
    return adapter.embed(request)
