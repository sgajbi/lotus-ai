from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.base import TextGenerationProviderAdapter
from app.providers.openai_compatible_text_transport import (
    OPENAI_MANAGED_TEXT_DESCRIPTOR,
    as_str as _as_str,
    build_structured_output as _build_structured_output,
    build_user_message as _build_user_message,
    extract_output_text as _extract_output_text,
    extract_usage as _extract_usage,
    post_openai_compatible_response as _post_openai_response_transport,
)


class OpenAILiveTextProvider(TextGenerationProviderAdapter):
    descriptor = OPENAI_MANAGED_TEXT_DESCRIPTOR

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
        output_message = _extract_output_text(response_payload)
        structured_output = _build_structured_output(
            descriptor=self.descriptor,
            request=request,
            response_payload=response_payload,
            output_message=output_message,
        )
        input_tokens, output_tokens, total_tokens = _extract_usage(response_payload)
        return ProviderExecutionResponse(
            provider_id=self.descriptor.provider_id,
            provider_mode=self.descriptor.runtime_mode.value,
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
            estimated_cost_usd=structured_output.get("estimated_cost_usd"),
            stubbed=False,
            message=output_message,
            structured_output=structured_output,
        )


def _post_openai_response(
    *,
    api_base: str,
    api_key: str | None,
    payload: dict[str, object],
    timeout_seconds: float,
) -> dict[str, object]:
    return _post_openai_response_transport(
        api_base=api_base,
        api_key=api_key,
        payload=payload,
        timeout_seconds=timeout_seconds,
        provider_display_name="OpenAI provider",
        require_api_key=True,
    )
