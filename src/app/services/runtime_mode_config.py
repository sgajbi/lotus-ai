"""Per-execution runtime mode configuration (issue #148, S4).

The retrieval, safety, and embedding subsystems read their operating modes
mid-request the same way the text-generation path once read its provider
settings. This module gives them the same shape S2 gave the provider path:
one frozen snapshot resolved from ``settings`` unless an execution-scoped
override is installed. The evaluation runtime installs a per-case override
instead of mutating process settings, so a concurrent production request
always runs under the deployed modes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class RuntimeModeConfig:
    retrieval_mode: str
    safety_mode: str
    embedding_provider_mode: str
    embedding_provider_id: str | None
    embedding_model_id: str | None
    embedding_api_key: str | None


_runtime_mode_config_override: ContextVar[RuntimeModeConfig | None] = ContextVar(
    "lotus_ai_runtime_mode_config_override", default=None
)


@contextmanager
def override_runtime_mode_config(config: RuntimeModeConfig) -> Iterator[None]:
    token = _runtime_mode_config_override.set(config)
    try:
        yield
    finally:
        _runtime_mode_config_override.reset(token)


def get_runtime_mode_config_override() -> RuntimeModeConfig | None:
    return _runtime_mode_config_override.get()


def resolve_runtime_mode_config() -> RuntimeModeConfig:
    override = _runtime_mode_config_override.get()
    if override is not None:
        return override
    return RuntimeModeConfig(
        retrieval_mode=settings.retrieval_mode,
        safety_mode=settings.safety_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        embedding_provider_id=settings.live_embedding_provider_id,
        embedding_model_id=settings.live_embedding_model_id,
        embedding_api_key=settings.live_embedding_provider_api_key,
    )
