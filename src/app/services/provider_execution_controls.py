from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class ProviderExecutionControls:
    timeout_ms: int
    retry_limit: int
    max_output_tokens: int
    temperature: float
    top_p: float | None
    seed: int | None


def build_provider_execution_controls() -> ProviderExecutionControls:
    return ProviderExecutionControls(
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
    execution configuration - including deterministic stub executions.
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
