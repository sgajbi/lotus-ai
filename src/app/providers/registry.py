from __future__ import annotations

from app.contracts.providers import (
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import (
    ProviderAdapterDescriptor,
    ProviderExecutionError,
    TextGenerationProviderAdapter,
)
from app.providers.openai_live_text_provider import OpenAILiveTextProvider
from app.providers.stub_text_provider import StubTextProvider

_stub_text_provider = StubTextProvider()
_openai_live_text_provider = OpenAILiveTextProvider()


def list_registered_provider_descriptors() -> list[ProviderAdapterDescriptor]:
    return [
        _stub_text_provider.descriptor,
        _openai_live_text_provider.descriptor,
    ]


def resolve_text_generation_adapter(
    mode: ProviderExecutionMode | str,
) -> TextGenerationProviderAdapter:
    if mode in {ProviderExecutionMode.DISABLED, ProviderExecutionMode.STUB}:
        return _stub_text_provider
    if mode == ProviderExecutionMode.OPENAI:
        return _openai_live_text_provider
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_NOT_REGISTERED,
        message=f"No text-generation provider adapter is registered for mode: {mode}",
    )
