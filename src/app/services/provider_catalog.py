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


def build_provider_catalog() -> ProviderCatalogResponse:
    providers = [
        ProviderDescriptor(
            provider_id=descriptor.provider_id,
            display_name=descriptor.display_name,
            capability=descriptor.capability,
            adapter_kind=descriptor.adapter_kind,
            lifecycle_status=ProviderLifecycleStatus.DOCUMENTED,
            runtime_mode=settings.provider_mode,
            enabled_for_execution=descriptor.enabled_for_execution,
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
        runtime_execution_enabled=any(provider.enabled_for_execution for provider in providers),
        providers=providers,
    )
