from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderCatalogResponse,
    ProviderDescriptor,
    ProviderFailureCategory,
    ProviderLifecycleStatus,
)
from app.providers.registry import list_registered_provider_descriptors
from app.services.provider_configuration_status import (
    build_text_generation_configuration_status,
)
from app.services.provider_live_execution_state import build_provider_live_execution_state


def build_provider_catalog() -> ProviderCatalogResponse:
    live_execution_state = build_provider_live_execution_state()
    providers = [
        ProviderDescriptor(
            provider_id=descriptor.provider_id,
            display_name=descriptor.display_name,
            capability=descriptor.capability,
            adapter_kind=descriptor.adapter_kind,
            lifecycle_status=ProviderLifecycleStatus.DOCUMENTED,
            runtime_mode=descriptor.runtime_mode.value,
            enabled_for_execution=(
                live_execution_state.live_execution_enabled
                if descriptor.provider_id == "text.openai"
                else descriptor.enabled_for_execution
            ),
            failure_category_on_use=descriptor.failure_category_on_use,
            source_reference=descriptor.source_reference,
            notes=descriptor.notes,
        )
        for descriptor in list_registered_provider_descriptors()
    ]
    providers.append(
        ProviderDescriptor(
            provider_id="embeddings.stub",
            display_name="Foundation Stub Embedding Provider",
            capability=ProviderCapability.EMBEDDINGS,
            adapter_kind=ProviderAdapterKind.STUB,
            lifecycle_status=ProviderLifecycleStatus.DOCUMENTED,
            runtime_mode=settings.embedding_provider_mode,
            enabled_for_execution=False,
            failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
            source_reference="docs/guides/retrieval-and-vector-store.md",
            notes=(
                "Embedding execution remains disabled until governed retrieval indexing and "
                "provider controls are fully implemented."
            ),
        )
    )
    return ProviderCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        text_generation_configuration=build_text_generation_configuration_status(),
        runtime_execution_enabled=any(provider.enabled_for_execution for provider in providers),
        providers=providers,
    )
