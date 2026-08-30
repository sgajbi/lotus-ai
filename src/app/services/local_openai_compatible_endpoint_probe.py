from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, cast
from urllib import error, request as urllib_request

from app.config import settings
from app.services.provider_execution_overrides import (
    ensure_network_execution_permitted,
    get_local_probe_status_override,
)


@dataclass(frozen=True)
class LocalOpenAICompatibleEndpointStatus:
    endpoint_reachable: bool
    model_available: bool
    configured_model_id: str | None
    blocking_reason: str | None


@dataclass
class _CachedProbeResult:
    cache_key: tuple[str, str | None, str | None]
    expires_at: float
    status: LocalOpenAICompatibleEndpointStatus


_cached_probe_result: _CachedProbeResult | None = None


def reset_local_openai_compatible_endpoint_probe_cache() -> None:
    global _cached_probe_result
    _cached_probe_result = None


def build_local_openai_compatible_endpoint_status() -> LocalOpenAICompatibleEndpointStatus:
    probe_override = get_local_probe_status_override()
    if probe_override is not None:
        return probe_override
    ensure_network_execution_permitted(
        seam="local_openai_compatible_endpoint_probe.build_local_openai_compatible_endpoint_status"
    )
    api_base = settings.live_text_api_base.strip().rstrip("/")
    configured_model_id = settings.live_text_model_id
    api_key = settings.live_text_provider_api_key
    cache_key = (api_base, configured_model_id, api_key)
    now = time.monotonic()

    global _cached_probe_result
    if (
        _cached_probe_result is not None
        and _cached_probe_result.cache_key == cache_key
        and _cached_probe_result.expires_at > now
    ):
        return _cached_probe_result.status

    status = _probe_local_openai_compatible_endpoint(
        api_base=api_base,
        configured_model_id=configured_model_id,
        api_key=api_key,
    )
    _cached_probe_result = _CachedProbeResult(
        cache_key=cache_key,
        expires_at=now + max(settings.live_text_local_probe_cache_seconds, 0),
        status=status,
    )
    return status


def _probe_local_openai_compatible_endpoint(
    *, api_base: str, configured_model_id: str | None, api_key: str | None
) -> LocalOpenAICompatibleEndpointStatus:
    if not configured_model_id:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=False,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason="Local OpenAI-compatible mode requires a configured model id.",
        )

    endpoint = api_base + "/models"
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib_request.Request(endpoint, headers=headers, method="GET")

    try:
        with urllib_request.urlopen(
            request,
            timeout=max(settings.live_text_local_probe_timeout_ms / 1000.0, 0.5),
        ) as response:
            payload = cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
    except TimeoutError:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=False,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason=(
                "Local OpenAI-compatible endpoint probe timed out before model readiness "
                "could be confirmed."
            ),
        )
    except error.HTTPError as exc:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=False,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason=(
                "Local OpenAI-compatible endpoint probe failed with HTTP "
                f"{exc.code} while checking model readiness."
            ),
        )
    except error.URLError as exc:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=False,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason=(
                f"Local OpenAI-compatible endpoint is not reachable from lotus-ai: {exc.reason}"
            ),
        )
    except json.JSONDecodeError:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=True,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason=(
                "Local OpenAI-compatible endpoint returned an unreadable model catalog."
            ),
        )

    model_ids = _extract_model_ids(payload)
    if model_ids is None:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=True,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason=(
                "Local OpenAI-compatible endpoint did not return a valid `/models` catalog."
            ),
        )
    if configured_model_id not in model_ids:
        return LocalOpenAICompatibleEndpointStatus(
            endpoint_reachable=True,
            model_available=False,
            configured_model_id=configured_model_id,
            blocking_reason=(
                "Configured local model id is not advertised by the local OpenAI-compatible "
                "endpoint."
            ),
        )
    return LocalOpenAICompatibleEndpointStatus(
        endpoint_reachable=True,
        model_available=True,
        configured_model_id=configured_model_id,
        blocking_reason=None,
    )


def _extract_model_ids(payload: dict[str, Any]) -> set[str] | None:
    data = payload.get("data")
    if not isinstance(data, list):
        return None
    model_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            return None
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            return None
        model_ids.add(model_id)
    return model_ids
