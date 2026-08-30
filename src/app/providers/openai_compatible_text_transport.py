from __future__ import annotations

import json
import logging
import time
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
from app.providers.base import ProviderAdapterDescriptor, ProviderExecutionError
from app.services.structured_logging import correlation_id_var, log_event
from app.providers.advisor_brief_quality_guardrails import (
    build_advisor_brief_user_message,
    normalize_advisor_brief_output,
)
from app.services.provider_usage_accounting import estimate_live_text_cost_usd


def execute_openai_compatible_text_request(
    *,
    descriptor: ProviderAdapterDescriptor,
    request: ProviderExecutionRequest,
    api_base: str,
    api_key: str | None,
    require_api_key: bool,
) -> ProviderExecutionResponse:
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
                "content": [{"type": "input_text", "text": build_user_message(request)}],
            },
        ],
        "max_output_tokens": request.max_output_tokens,
    }
    response_payload = post_openai_compatible_response(
        api_base=api_base,
        api_key=api_key,
        payload=payload,
        timeout_seconds=max(request.timeout_ms / 1000.0, 1.0),
        provider_display_name=descriptor.display_name,
        require_api_key=require_api_key,
        retry_limit=request.retry_limit,
    )
    output_message = extract_output_text(response_payload)
    message, structured_output = build_structured_output(
        descriptor=descriptor,
        request=request,
        response_payload=response_payload,
        output_message=output_message,
    )
    input_tokens, output_tokens, total_tokens = extract_usage(response_payload)
    return ProviderExecutionResponse(
        provider_id=descriptor.provider_id,
        provider_mode=descriptor.runtime_mode.value,
        adapter_kind=descriptor.adapter_kind,
        failure_category=None,
        timeout_ms=request.timeout_ms,
        retry_count=extract_retry_count(response_payload),
        max_output_tokens=request.max_output_tokens,
        model_id=as_str(response_payload.get("model")) or settings.live_text_model_id,
        model_version=settings.live_text_model_version,
        provider_request_id=as_str(response_payload.get("id")),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_live_text_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        stubbed=False,
        message=message,
        structured_output=structured_output,
    )


def build_user_message(request: ProviderExecutionRequest) -> str:
    if is_advisor_brief_payload(request.context_payload):
        return build_advisor_brief_user_message(
            task_id=request.task_id,
            caller_app=request.caller_app,
            context_summary=request.context_summary,
            context_payload=request.context_payload,
            source_refs=request.source_refs,
        )
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


def post_openai_compatible_response(
    *,
    api_base: str,
    api_key: str | None,
    payload: dict[str, object],
    timeout_seconds: float,
    provider_display_name: str,
    require_api_key: bool,
    retry_limit: int = 0,
) -> dict[str, Any]:
    if require_api_key and api_key is None:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_LIVE_CONFIGURATION,
            message=f"Live provider credentials are not configured for {provider_display_name}.",
        )
    endpoint = api_base.rstrip("/") + "/responses"
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    correlation_id = correlation_id_var.get()
    if correlation_id is not None:
        headers["X-Correlation-Id"] = correlation_id
    model_identity = payload.get("model")
    bounded_retry_limit = max(retry_limit, 0)
    for attempt_index in range(bounded_retry_limit + 1):
        provider_request = urllib_request.Request(
            endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        attempt_started = time.perf_counter()
        try:
            with urllib_request.urlopen(provider_request, timeout=timeout_seconds) as response:
                response_payload = cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
                response_payload["_lotus_retry_count"] = attempt_index
                usage = response_payload.get("usage")
                usage_fields = usage if isinstance(usage, dict) else {}
                log_event(
                    _logger,
                    "provider_attempt",
                    provider_id=provider_display_name,
                    model_id=model_identity,
                    attempt=attempt_index,
                    attempt_limit=bounded_retry_limit,
                    outcome="success",
                    latency_ms=_attempt_latency_ms(attempt_started),
                    input_tokens=usage_fields.get("input_tokens"),
                    output_tokens=usage_fields.get("output_tokens"),
                )
                return response_payload
        except error.HTTPError as exc:
            load_error_payload(exc)
            category = failure_category_for_http_status(exc.code)
            retryable = is_retryable_provider_failure(category=category, http_status_code=exc.code)
            will_retry = retryable and attempt_index < bounded_retry_limit
            log_event(
                _logger,
                "provider_attempt",
                provider_id=provider_display_name,
                model_id=model_identity,
                attempt=attempt_index,
                attempt_limit=bounded_retry_limit,
                outcome="retry" if will_retry else "failed",
                failure_class=category.value,
                http_status=exc.code,
                latency_ms=_attempt_latency_ms(attempt_started),
            )
            if will_retry:
                continue
            raise ProviderExecutionError(
                category=category,
                message=safe_provider_error_message(
                    category=category,
                    provider_display_name=provider_display_name,
                ),
            ) from exc
        except TimeoutError as exc:
            will_retry = attempt_index < bounded_retry_limit
            log_event(
                _logger,
                "provider_attempt",
                provider_id=provider_display_name,
                model_id=model_identity,
                attempt=attempt_index,
                attempt_limit=bounded_retry_limit,
                outcome="retry" if will_retry else "failed",
                failure_class=ProviderFailureCategory.PROVIDER_TIMEOUT.value,
                latency_ms=_attempt_latency_ms(attempt_started),
            )
            if will_retry:
                continue
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                message=safe_provider_error_message(
                    category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                    provider_display_name=provider_display_name,
                ),
            ) from exc
        except error.URLError as exc:
            will_retry = attempt_index < bounded_retry_limit
            log_event(
                _logger,
                "provider_attempt",
                provider_id=provider_display_name,
                model_id=model_identity,
                attempt=attempt_index,
                attempt_limit=bounded_retry_limit,
                outcome="retry" if will_retry else "failed",
                failure_class=ProviderFailureCategory.PROVIDER_TIMEOUT.value,
                latency_ms=_attempt_latency_ms(attempt_started),
            )
            if will_retry:
                continue
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                message=safe_provider_error_message(
                    category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                    provider_display_name=provider_display_name,
                ),
            ) from exc
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        message=safe_provider_error_message(
            category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
            provider_display_name=provider_display_name,
        ),
    )


_logger = logging.getLogger("app.provider")


def _attempt_latency_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def load_error_payload(exc: error.HTTPError) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(exc.read().decode("utf-8")))
    except json.JSONDecodeError:
        return {}


def failure_category_for_http_status(http_status_code: int) -> ProviderFailureCategory:
    if http_status_code == 429:
        return ProviderFailureCategory.PROVIDER_RATE_LIMITED
    return ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR


def is_retryable_provider_failure(
    *, category: ProviderFailureCategory, http_status_code: int | None = None
) -> bool:
    if category in {
        ProviderFailureCategory.PROVIDER_TIMEOUT,
        ProviderFailureCategory.PROVIDER_RATE_LIMITED,
    }:
        return True
    return category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR and http_status_code in {
        408,
        500,
        502,
        503,
        504,
    }


def safe_provider_error_message(
    *, category: ProviderFailureCategory, provider_display_name: str
) -> str:
    if category == ProviderFailureCategory.PROVIDER_RATE_LIMITED:
        return f"{provider_display_name} rate limit exceeded."
    if category == ProviderFailureCategory.PROVIDER_TIMEOUT:
        return f"{provider_display_name} request did not complete within the configured timeout."
    return f"{provider_display_name} request failed at the upstream provider boundary."


def extract_output_text(payload: dict[str, Any]) -> str:
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
        message="OpenAI-compatible provider response did not include output text.",
    )


def extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return (None, None, None)
    return (
        as_int(usage.get("input_tokens")),
        as_int(usage.get("output_tokens")),
        as_int(usage.get("total_tokens")),
    )


def extract_retry_count(payload: dict[str, Any]) -> int:
    return as_int(payload.get("_lotus_retry_count")) or 0


def as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def as_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def is_advisor_brief_payload(payload: dict[str, Any]) -> bool:
    return {"portfolio", "period", "performance", "supportability"}.issubset(payload.keys())


def build_structured_output(
    *,
    descriptor: ProviderAdapterDescriptor,
    request: ProviderExecutionRequest,
    response_payload: dict[str, Any],
    output_message: str,
) -> tuple[str, dict[str, Any]]:
    structured_output: dict[str, Any] = {
        "provider_id": descriptor.provider_id,
        "provider_mode": descriptor.runtime_mode.value,
        "adapter_kind": descriptor.adapter_kind.value,
        "model_id": as_str(response_payload.get("model")) or settings.live_text_model_id,
        "provider_request_id": as_str(response_payload.get("id")),
        "output_label": request.output_label,
        "safety_mode": request.safety_mode,
        "redaction_posture": request.redaction_posture,
        "source_refs": request.source_refs,
        "retry_count": extract_retry_count(response_payload),
    }
    input_tokens, output_tokens, total_tokens = extract_usage(response_payload)
    structured_output.update(
        {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimate_live_text_cost_usd(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        }
    )
    if not is_advisor_brief_payload(request.context_payload):
        return output_message, structured_output

    parsed = parse_json_object(output_message)
    quality_result = normalize_advisor_brief_output(
        parsed_output=parsed,
        output_message=output_message,
        context_payload=request.context_payload,
        source_refs=request.source_refs,
    )
    structured_output.update(quality_result.structured_output)
    return quality_result.message, structured_output


def parse_json_object(value: str) -> dict[str, Any] | None:
    normalized = strip_json_code_fence(value)
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        candidate = extract_balanced_json_object(normalized)
        if candidate is None:
            return None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def strip_json_code_fence(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("```json"):
        return normalized.removeprefix("```json").removesuffix("```").strip()
    if normalized.startswith("```"):
        return normalized.removeprefix("```").removesuffix("```").strip()
    return normalized


def extract_balanced_json_object(value: str) -> str | None:
    start = value.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(value[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]
    return None


OPENAI_MANAGED_TEXT_DESCRIPTOR = ProviderAdapterDescriptor(
    provider_id="text.openai",
    display_name="OpenAI Managed Text Provider",
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


LOCAL_OPENAI_COMPATIBLE_TEXT_DESCRIPTOR = ProviderAdapterDescriptor(
    provider_id="text.local",
    display_name="Local OpenAI-Compatible Text Provider",
    capability=ProviderCapability.TEXT_GENERATION,
    adapter_kind=ProviderAdapterKind.OPENAI_COMPATIBLE_LOCAL,
    runtime_mode=ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE,
    enabled_for_execution=False,
    failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
    source_reference="docs/rfcs/RFC-0027-local-and-remote-openai-compatible-provider-routing.md",
    notes=(
        "Governed local or self-hosted OpenAI-compatible text-generation path for private "
        "deployment, developer-local validation, and billing-controlled execution."
    ),
)
