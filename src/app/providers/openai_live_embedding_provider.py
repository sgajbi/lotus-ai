from __future__ import annotations

import json
from typing import Any, cast
from urllib import error, request as urllib_request

from app.config import settings
from app.contracts.providers import (
    EmbeddingExecutionRequest,
    EmbeddingExecutionResponse,
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import ProviderAdapterDescriptor, ProviderExecutionError
from app.providers.openai_compatible_text_transport import (
    failure_category_for_http_status,
    safe_provider_error_message,
)


class OpenAILiveEmbeddingProvider:
    descriptor = ProviderAdapterDescriptor(
        provider_id="embeddings.openai",
        display_name="OpenAI Live Embedding Provider",
        capability=ProviderCapability.EMBEDDINGS,
        adapter_kind=ProviderAdapterKind.OPENAI_EMBEDDINGS_LIVE,
        runtime_mode=ProviderExecutionMode.ENABLED,
        enabled_for_execution=False,
        failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
        source_reference="docs/rfcs/RFC-0018-governed-embeddings-and-provider-expansion.md",
        notes=(
            "Live embedding adapter is registered and inspectable, but execution remains blocked "
            "until a later RFC-0018 slice completes retrieval/provider governance activation."
        ),
    )

    def embed(self, request: EmbeddingExecutionRequest) -> EmbeddingExecutionResponse:
        response_payload = _post_openai_embedding(
            api_base=settings.live_text_api_base,
            api_key=settings.live_embedding_provider_api_key,
            payload={
                "model": settings.live_embedding_model_id,
                "input": request.content,
            },
        )
        embedding = _extract_embedding(response_payload)
        model_id = _as_str(response_payload.get("model")) or settings.live_embedding_model_id
        return EmbeddingExecutionResponse(
            provider_id=self.descriptor.provider_id,
            provider_mode=self.descriptor.runtime_mode.value,
            adapter_kind=self.descriptor.adapter_kind,
            failure_category=None,
            model_id=model_id,
            stubbed=False,
            vector_dimension=len(embedding),
            embedding=embedding,
            message=(
                "Live OpenAI embedding execution completed successfully for the bounded "
                f"request from caller {request.caller_app}."
            ),
        )


def _post_openai_embedding(
    *,
    api_base: str,
    api_key: str | None,
    payload: dict[str, object],
) -> dict[str, Any]:
    if api_key is None:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_LIVE_CONFIGURATION,
            message="Live embedding provider credentials are not configured for OpenAI execution.",
        )
    endpoint = api_base.rstrip("/") + "/embeddings"
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
        with urllib_request.urlopen(
            request, timeout=max(settings.provider_timeout_ms / 1000.0, 1.0)
        ) as response:
            return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
    except error.HTTPError as exc:
        _load_error_payload(exc)
        category = failure_category_for_http_status(exc.code)
        raise ProviderExecutionError(
            category=category,
            message=safe_provider_error_message(
                category=category,
                provider_display_name="OpenAI embedding provider",
            ),
        ) from exc
    except TimeoutError as exc:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            message=safe_provider_error_message(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                provider_display_name="OpenAI embedding provider",
            ),
        ) from exc
    except error.URLError as exc:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            message=safe_provider_error_message(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                provider_display_name="OpenAI embedding provider",
            ),
        ) from exc


def _load_error_payload(exc: error.HTTPError) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(exc.read().decode("utf-8")))
    except json.JSONDecodeError:
        return {}


def _extract_embedding(payload: dict[str, Any]) -> list[float]:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict):
            embedding = first_item.get("embedding")
            if isinstance(embedding, list) and all(
                isinstance(value, int | float) for value in embedding
            ):
                return [float(value) for value in embedding]
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        message="OpenAI embedding provider response did not include an embedding vector.",
    )


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
