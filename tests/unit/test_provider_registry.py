import pytest

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.providers.registry import (
    list_registered_provider_descriptors,
    resolve_embedding_adapter,
    resolve_text_generation_adapter,
)


def test_provider_registry_lists_text_and_embedding_descriptors() -> None:
    descriptors = list_registered_provider_descriptors()

    assert any(
        descriptor.provider_id == "text.stub"
        and descriptor.adapter_kind == ProviderAdapterKind.STUB
        for descriptor in descriptors
    )
    assert any(
        descriptor.provider_id == "text.openai"
        and descriptor.adapter_kind == ProviderAdapterKind.OPENAI_LIVE
        and descriptor.failure_category_on_use == ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
        for descriptor in descriptors
    )
    assert any(
        descriptor.provider_id == "embeddings.stub"
        and descriptor.adapter_kind == ProviderAdapterKind.STUB
        for descriptor in descriptors
    )
    assert any(
        descriptor.provider_id == "embeddings.openai"
        and descriptor.adapter_kind == ProviderAdapterKind.OPENAI_EMBEDDINGS_LIVE
        and descriptor.failure_category_on_use == ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
        for descriptor in descriptors
    )


def test_provider_registry_resolves_stub_adapter_for_supported_modes() -> None:
    disabled_adapter = resolve_text_generation_adapter(ProviderExecutionMode.DISABLED)
    stub_adapter = resolve_text_generation_adapter(ProviderExecutionMode.STUB)

    assert disabled_adapter.descriptor.provider_id == "text.stub"
    assert stub_adapter.descriptor.provider_id == "text.stub"


def test_provider_registry_rejects_unregistered_mode() -> None:
    with pytest.raises(ProviderExecutionError) as exc_info:
        resolve_text_generation_adapter("unsupported")

    assert exc_info.value.category == ProviderFailureCategory.PROVIDER_NOT_REGISTERED


def test_provider_registry_resolves_embedding_adapters_for_supported_modes() -> None:
    disabled_adapter = resolve_embedding_adapter(ProviderExecutionMode.DISABLED)
    stub_adapter = resolve_embedding_adapter(ProviderExecutionMode.STUB)
    live_adapter = resolve_embedding_adapter(ProviderExecutionMode.ENABLED)

    assert disabled_adapter.descriptor.provider_id == "embeddings.stub"
    assert stub_adapter.descriptor.provider_id == "embeddings.stub"
    assert live_adapter.descriptor.provider_id == "embeddings.openai"
