from __future__ import annotations

from app.contracts.providers import (
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import (
    EmbeddingProviderAdapter,
    ProviderAdapterDescriptor,
    ProviderExecutionError,
    TextGenerationProviderAdapter,
)
from app.providers.local_openai_compatible_text_provider import (
    LocalOpenAICompatibleTextProvider,
)
from app.providers.openai_live_embedding_provider import OpenAILiveEmbeddingProvider
from app.providers.openai_live_text_provider import OpenAILiveTextProvider
from app.providers.stub_embedding_provider import StubEmbeddingProvider
from app.providers.stub_text_provider import StubTextProvider

_stub_text_provider = StubTextProvider()
_openai_live_text_provider = OpenAILiveTextProvider()
_local_openai_compatible_text_provider = LocalOpenAICompatibleTextProvider()
_stub_embedding_provider = StubEmbeddingProvider()
_openai_live_embedding_provider = OpenAILiveEmbeddingProvider()


def list_registered_provider_descriptors() -> list[ProviderAdapterDescriptor]:
    return [
        _stub_text_provider.descriptor,
        _openai_live_text_provider.descriptor,
        _local_openai_compatible_text_provider.descriptor,
        _stub_embedding_provider.descriptor,
        _openai_live_embedding_provider.descriptor,
    ]


def resolve_text_generation_adapter(
    mode: ProviderExecutionMode | str,
) -> TextGenerationProviderAdapter:
    if mode in {ProviderExecutionMode.DISABLED, ProviderExecutionMode.STUB}:
        return _stub_text_provider
    if mode == ProviderExecutionMode.OPENAI:
        return _openai_live_text_provider
    if mode == ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE:
        return _local_openai_compatible_text_provider
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_NOT_REGISTERED,
        message=f"No text-generation provider adapter is registered for mode: {mode}",
    )


def resolve_embedding_adapter(mode: ProviderExecutionMode | str) -> EmbeddingProviderAdapter:
    if mode in {ProviderExecutionMode.DISABLED, ProviderExecutionMode.STUB}:
        return _stub_embedding_provider
    if mode == ProviderExecutionMode.ENABLED:
        return _openai_live_embedding_provider
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_NOT_REGISTERED,
        message=f"No embedding provider adapter is registered for mode: {mode}",
    )
