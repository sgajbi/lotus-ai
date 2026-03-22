from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class ProviderExecutionControls:
    timeout_ms: int
    retry_limit: int
    max_output_tokens: int


def build_provider_execution_controls() -> ProviderExecutionControls:
    return ProviderExecutionControls(
        timeout_ms=max(settings.provider_timeout_ms, 1),
        retry_limit=max(settings.provider_retry_limit, 0),
        max_output_tokens=max(settings.provider_max_output_tokens, 1),
    )
