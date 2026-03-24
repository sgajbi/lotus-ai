from __future__ import annotations

from app.contracts.providers import (
    EmbeddingExecutionRequest,
    EmbeddingExecutionResponse,
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import ProviderAdapterDescriptor, ProviderExecutionError


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
        raise ProviderExecutionError(
            category=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
            message=(
                "Live embedding execution is registered but not yet enabled in the current "
                f"delivery phase for caller {request.caller_app}."
            ),
        )
