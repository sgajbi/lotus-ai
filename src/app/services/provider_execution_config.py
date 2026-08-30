"""Per-request provider execution configuration (issue #148, S2).

Production text-generation execution used to read ~10 ``settings`` attributes
at scattered points mid-request, which is why the evaluation runtime mutated
the process-wide settings singleton to run a case. This module gives the
execution path one immutable snapshot instead:

- ``resolve_provider_execution_config()`` builds a frozen config from
  ``settings`` - the production path - unless an execution-scoped override is
  installed, in which case the override IS the config.
- The evaluation runtime installs a per-case config through
  ``override_provider_execution_config`` (contextvar-scoped, like the seam
  overrides in ``provider_execution_overrides``), so a concurrent production
  request never observes an eval case's provider configuration.

The config deliberately carries only the text-generation execution surface:
mode, rollout, model identity, endpoint, credential, task allowlist, and the
execution controls (issue #151 sampling included). Enforcement thresholds
(quota/budget/degradation) remain settings-read until S3.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class ProviderExecutionConfig:
    provider_mode: str
    rollout_state: str
    provider_id: str | None
    model_id: str | None
    model_version: str | None
    api_base: str
    api_key: str | None
    allowed_task_ids: str
    timeout_ms: int
    retry_limit: int
    max_output_tokens: int
    temperature: float
    top_p: float | None
    seed: int | None


_provider_execution_config_override: ContextVar[ProviderExecutionConfig | None] = ContextVar(
    "lotus_ai_provider_execution_config_override", default=None
)


@contextmanager
def override_provider_execution_config(config: ProviderExecutionConfig) -> Iterator[None]:
    token = _provider_execution_config_override.set(config)
    try:
        yield
    finally:
        _provider_execution_config_override.reset(token)


def get_provider_execution_config_override() -> ProviderExecutionConfig | None:
    return _provider_execution_config_override.get()


def resolve_provider_execution_config() -> ProviderExecutionConfig:
    override = _provider_execution_config_override.get()
    if override is not None:
        return override
    return ProviderExecutionConfig(
        provider_mode=settings.provider_mode,
        rollout_state=settings.provider_rollout_state,
        provider_id=settings.live_text_provider_id,
        model_id=settings.live_text_model_id,
        model_version=settings.live_text_model_version,
        api_base=settings.live_text_api_base,
        api_key=settings.live_text_provider_api_key,
        allowed_task_ids=settings.live_text_allowed_task_ids,
        timeout_ms=max(settings.provider_timeout_ms, 1),
        retry_limit=max(settings.provider_retry_limit, 0),
        max_output_tokens=max(settings.provider_max_output_tokens, 1),
        temperature=settings.live_text_temperature,
        top_p=settings.live_text_top_p,
        seed=settings.live_text_seed,
    )


def compute_provider_config_sha256(
    *,
    provider_mode: str,
    provider_id: str | None,
    model_id: str | None,
    model_version: str | None,
    temperature: float,
    top_p: float | None,
    seed: int | None,
    max_output_tokens: int,
) -> str:
    """Digest of the resolved execution configuration (issue #151).

    Covers the model identity and the sampling configuration that shaped the
    call, so two audit rows with the same digest were produced under the same
    execution configuration - including deterministic stub executions. The
    credential is deliberately excluded.
    """

    canonical = json.dumps(
        {
            "provider_mode": provider_mode,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_version": model_version,
            "temperature": temperature,
            "top_p": top_p,
            "seed": seed,
            "max_output_tokens": max_output_tokens,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
