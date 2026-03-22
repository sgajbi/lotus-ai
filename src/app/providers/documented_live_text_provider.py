from __future__ import annotations

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import (
    ProviderAdapterDescriptor,
    ProviderExecutionError,
    TextGenerationProviderAdapter,
)


class DocumentedLiveTextProvider(TextGenerationProviderAdapter):
    descriptor = ProviderAdapterDescriptor(
        provider_id="text.live_documented",
        display_name="Documented Live Text Provider",
        capability=ProviderCapability.TEXT_GENERATION,
        adapter_kind=ProviderAdapterKind.DOCUMENTED_LIVE,
        runtime_mode=ProviderExecutionMode.DISABLED,
        enabled_for_execution=False,
        failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
        source_reference="docs/rfcs/RFC-0003-controlled-live-provider-backbone.md",
        notes=(
            "Documented live-provider seam for future governed activation. "
            "No live text-generation provider is enabled in the current phase."
        ),
    )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
            message=(
                "A live text-generation provider is documented, but no governed live "
                "provider path is enabled in the current phase."
            ),
        )
