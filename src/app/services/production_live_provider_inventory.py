from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.providers import ProviderExecutionMode


@dataclass(frozen=True)
class LiveProviderCapability:
    capability_id: str
    label: str
    configured_mode: str
    secret_configured: bool
    execution_requested: bool


@dataclass(frozen=True)
class LiveProviderInventory:
    capabilities: tuple[LiveProviderCapability, ...]

    @property
    def execution_requested(self) -> bool:
        return any(capability.execution_requested for capability in self.capabilities)

    @property
    def secret_capability_labels(self) -> tuple[str, ...]:
        return tuple(
            capability.label for capability in self.capabilities if capability.secret_configured
        )

    @property
    def execution_capability_labels(self) -> tuple[str, ...]:
        return tuple(
            capability.label for capability in self.capabilities if capability.execution_requested
        )

    @property
    def configured_mode_summary(self) -> str:
        return ", ".join(
            f"{capability.capability_id}:{capability.configured_mode}"
            for capability in self.capabilities
        )


def build_live_provider_inventory() -> LiveProviderInventory:
    return LiveProviderInventory(
        capabilities=(
            LiveProviderCapability(
                capability_id="text_generation",
                label="text generation",
                configured_mode=settings.provider_mode,
                secret_configured=bool(settings.live_text_provider_api_key),
                execution_requested=settings.provider_mode
                in {
                    ProviderExecutionMode.OPENAI.value,
                    ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
                },
            ),
            LiveProviderCapability(
                capability_id="embeddings",
                label="embeddings",
                configured_mode=resolve_runtime_mode_config().embedding_provider_mode,
                secret_configured=bool(resolve_runtime_mode_config().embedding_api_key),
                execution_requested=resolve_runtime_mode_config().embedding_provider_mode
                == ProviderExecutionMode.ENABLED.value,
            ),
        )
    )
