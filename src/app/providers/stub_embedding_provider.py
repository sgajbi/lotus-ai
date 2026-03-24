from __future__ import annotations

from app.contracts.providers import (
    EmbeddingExecutionRequest,
    EmbeddingExecutionResponse,
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
)
from app.providers.base import ProviderAdapterDescriptor


class StubEmbeddingProvider:
    descriptor = ProviderAdapterDescriptor(
        provider_id="embeddings.stub",
        display_name="Foundation Stub Embedding Provider",
        capability=ProviderCapability.EMBEDDINGS,
        adapter_kind=ProviderAdapterKind.STUB,
        runtime_mode=ProviderExecutionMode.STUB,
        enabled_for_execution=False,
        source_reference="docs/guides/retrieval-and-vector-store.md",
        notes=(
            "Stub embedding execution remains available for contract and catalog validation while "
            "governed live embedding rollout is still below activation."
        ),
    )

    def embed(self, request: EmbeddingExecutionRequest) -> EmbeddingExecutionResponse:
        bounded_length = min(8, max(1, len(request.content.split())))
        return EmbeddingExecutionResponse(
            provider_id=self.descriptor.provider_id,
            provider_mode=self.descriptor.runtime_mode.value,
            adapter_kind=self.descriptor.adapter_kind,
            failure_category=None,
            model_id="stub-embedding-v1",
            stubbed=True,
            vector_dimension=bounded_length,
            embedding=[0.0] * bounded_length,
            message="Stub embedding response produced for governed contract validation.",
        )
