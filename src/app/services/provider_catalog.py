from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderCapability,
    ProviderCatalogResponse,
    ProviderDescriptor,
    ProviderLifecycleStatus,
)
from app.providers.registry import list_registered_provider_descriptors
from app.services.embedding_live_execution_state import build_embedding_live_execution_state
from app.services.provider_expansion_policy import build_provider_expansion_policy
from app.services.provider_configuration_status import (
    build_embedding_configuration_status,
    build_text_generation_configuration_status,
)
from app.services.provider_live_execution_state import build_provider_live_execution_state


def build_provider_catalog() -> ProviderCatalogResponse:
    live_execution_state = build_provider_live_execution_state()
    embedding_live_execution_state = build_embedding_live_execution_state()
    text_generation_configuration = build_text_generation_configuration_status()
    embedding_configuration = build_embedding_configuration_status()
    expansion_policy = build_provider_expansion_policy()
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
                else (
                    embedding_live_execution_state.live_execution_enabled
                    if descriptor.provider_id == "embeddings.openai"
                    else descriptor.enabled_for_execution
                )
            ),
            failure_category_on_use=descriptor.failure_category_on_use,
            source_reference=descriptor.source_reference,
            notes=descriptor.notes,
        )
        for descriptor in list_registered_provider_descriptors()
    ]
    text_generation_runtime_execution_enabled = any(
        provider.enabled_for_execution
        for provider in providers
        if provider.capability == ProviderCapability.TEXT_GENERATION
    )
    embedding_runtime_execution_enabled = any(
        provider.enabled_for_execution
        for provider in providers
        if provider.capability == ProviderCapability.EMBEDDINGS
    )
    return ProviderCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        text_generation_configuration=text_generation_configuration,
        embedding_configuration=embedding_configuration,
        runtime_execution_enabled=text_generation_runtime_execution_enabled
        or embedding_runtime_execution_enabled,
        text_generation_runtime_execution_enabled=text_generation_runtime_execution_enabled,
        embedding_runtime_execution_enabled=embedding_runtime_execution_enabled,
        expansion_policy=expansion_policy,
        providers=providers,
    )
