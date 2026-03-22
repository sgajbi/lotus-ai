from __future__ import annotations

import json
from typing import Any, cast
from urllib import error, request as urllib_request

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderFailureCategory,
)
from app.providers.base import (
    ProviderAdapterDescriptor,
    ProviderExecutionError,
    TextGenerationProviderAdapter,
)
from app.services.provider_usage_accounting import estimate_live_text_cost_usd


class OpenAILiveTextProvider(TextGenerationProviderAdapter):
    descriptor = ProviderAdapterDescriptor(
        provider_id="text.openai",
        display_name="OpenAI Live Text Provider",
        capability=ProviderCapability.TEXT_GENERATION,
        adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
        runtime_mode=ProviderExecutionMode.OPENAI,
        enabled_for_execution=False,
        failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
        source_reference="docs/rfcs/RFC-0003-controlled-live-provider-backbone.md",
        notes=(
            "Allowlisted OpenAI-backed live text-generation path. Runtime activation remains "
            "disabled by default until rollout, allowlist, and governance gates are satisfied."
        ),
    )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        payload: dict[str, object] = {
            "model": settings.live_text_model_id,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"{request.system_instructions}\n\n"
                                f"Output contract notes:\n{request.output_contract_notes}"
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": _build_user_message(request)}],
                },
            ],
            "max_output_tokens": request.max_output_tokens,
        }
        response_payload = _post_openai_response(
            api_base=settings.live_text_api_base,
            api_key=settings.live_text_provider_api_key,
            payload=payload,
            timeout_seconds=max(request.timeout_ms / 1000.0, 1.0),
        )
        input_tokens, output_tokens, total_tokens = _extract_usage(response_payload)
        return ProviderExecutionResponse(
            provider_id=self.descriptor.provider_id,
            provider_mode=ProviderExecutionMode.OPENAI.value,
            adapter_kind=self.descriptor.adapter_kind,
            failure_category=None,
            timeout_ms=request.timeout_ms,
            retry_count=0,
            max_output_tokens=request.max_output_tokens,
            model_id=_as_str(response_payload.get("model")) or settings.live_text_model_id,
            provider_request_id=_as_str(response_payload.get("id")),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimate_live_text_cost_usd(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            stubbed=False,
            message=_extract_output_text(response_payload),
            structured_output={
                "provider_id": self.descriptor.provider_id,
                "provider_mode": ProviderExecutionMode.OPENAI.value,
                "adapter_kind": self.descriptor.adapter_kind.value,
                "model_id": _as_str(response_payload.get("model")) or settings.live_text_model_id,
                "provider_request_id": _as_str(response_payload.get("id")),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": estimate_live_text_cost_usd(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                ),
                "output_label": request.output_label,
                "safety_mode": request.safety_mode,
                "redaction_posture": request.redaction_posture,
                "source_refs": request.source_refs,
            },
        )


def _build_user_message(request: ProviderExecutionRequest) -> str:
    return json.dumps(
        {
            "task_id": request.task_id,
            "caller_app": request.caller_app,
            "context_summary": request.context_summary,
            "context_payload": request.context_payload,
            "source_refs": request.source_refs,
        },
        indent=2,
        sort_keys=True,
    )


def _post_openai_response(
    *,
    api_base: str,
    api_key: str | None,
    payload: dict[str, object],
    timeout_seconds: float,
) -> dict[str, Any]:
    if api_key is None:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_LIVE_CONFIGURATION,
            message="Live provider credentials are not configured for OpenAI execution.",
        )
    endpoint = api_base.rstrip("/") + "/responses"
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
    except error.HTTPError as exc:
        payload = _load_error_payload(exc)
        if exc.code == 429:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_RATE_LIMITED,
                message=_extract_error_message(
                    payload, fallback="OpenAI provider rate limit exceeded."
                ),
            ) from exc
        raise ProviderExecutionError(
            category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
            message=_extract_error_message(payload, fallback="OpenAI provider request failed."),
        ) from exc
    except TimeoutError as exc:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            message="OpenAI provider request exceeded the configured timeout.",
        ) from exc
    except error.URLError as exc:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            message=f"OpenAI provider request failed before completion: {exc.reason}",
        ) from exc


def _load_error_payload(exc: error.HTTPError) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(exc.read().decode("utf-8")))
    except json.JSONDecodeError:
        return {}


def _extract_error_message(payload: dict[str, Any], *, fallback: str) -> str:
    error_payload = payload.get("error")
    if isinstance(error_payload, dict):
        message = error_payload.get("message")
        if isinstance(message, str) and message.strip():
            return message
    return fallback


def _extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    output = payload.get("output")
    if isinstance(output, list):
        fragments: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    fragments.append(text.strip())
        if fragments:
            return "\n".join(fragments)
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        message="OpenAI provider response did not include output text.",
    )


def _extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return (None, None, None)
    return (
        _as_int(usage.get("input_tokens")),
        _as_int(usage.get("output_tokens")),
        _as_int(usage.get("total_tokens")),
    )


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
