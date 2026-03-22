from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderExecutionMode,
    ProviderFailureCategory,
)


@dataclass(frozen=True)
class ProviderAdapterDescriptor:
    provider_id: str
    display_name: str
    capability: ProviderCapability
    adapter_kind: ProviderAdapterKind
    runtime_mode: ProviderExecutionMode
    enabled_for_execution: bool
    source_reference: str
    notes: str
    failure_category_on_use: ProviderFailureCategory | None = None


class ProviderExecutionError(RuntimeError):
    def __init__(self, *, category: ProviderFailureCategory, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message


class TextGenerationProviderAdapter(Protocol):
    descriptor: ProviderAdapterDescriptor

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse: ...
