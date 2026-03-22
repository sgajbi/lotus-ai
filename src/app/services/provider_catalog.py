from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderCapability,
    ProviderCatalogResponse,
    ProviderDescriptor,
    ProviderLifecycleStatus,
)


def build_provider_catalog() -> ProviderCatalogResponse:
    providers = [
        ProviderDescriptor(
            provider_id="text.stub",
            display_name="Foundation Stub Text Provider",
            capability=ProviderCapability.TEXT_GENERATION,
            lifecycle_status=ProviderLifecycleStatus.DOCUMENTED,
            runtime_mode=settings.provider_mode,
            enabled_for_execution=False,
            source_reference="app.services.task_executor",
            notes=(
                "Foundation-phase deterministic placeholder execution path used for contract "
                "validation and audit behavior."
            ),
        ),
        ProviderDescriptor(
            provider_id="embeddings.stub",
            display_name="Foundation Stub Embedding Provider",
            capability=ProviderCapability.EMBEDDINGS,
            lifecycle_status=ProviderLifecycleStatus.DOCUMENTED,
            runtime_mode=settings.embedding_provider_mode,
            enabled_for_execution=False,
            source_reference="docs/guides/retrieval-and-vector-store.md",
            notes=(
                "Embedding execution remains disabled until governed retrieval indexing and "
                "provider controls are fully implemented."
            ),
        ),
    ]
    return ProviderCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        runtime_execution_enabled=any(provider.enabled_for_execution for provider in providers),
        providers=providers,
    )
