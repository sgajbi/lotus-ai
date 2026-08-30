from __future__ import annotations

from dataclasses import dataclass

from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.providers import ProviderCredentialStatus, ProviderExecutionMode
from app.services.provider_configuration_status import build_embedding_configuration_status


@dataclass(frozen=True)
class EmbeddingLiveExecutionState:
    provider_mode: str
    configuration_valid: bool
    credentials_configured: bool
    mode_supported: bool
    live_mode_requested: bool
    live_execution_enabled: bool
    configured_provider_id: str | None
    configured_model_id: str | None
    blocking_reason: str | None


def build_embedding_live_execution_state() -> EmbeddingLiveExecutionState:
    configuration = build_embedding_configuration_status()
    mode_supported = resolve_runtime_mode_config().embedding_provider_mode in {
        ProviderExecutionMode.DISABLED.value,
        ProviderExecutionMode.STUB.value,
        ProviderExecutionMode.ENABLED.value,
    }
    live_mode_requested = (
        resolve_runtime_mode_config().embedding_provider_mode == ProviderExecutionMode.ENABLED.value
    )
    credentials_configured = configuration.credential_status == ProviderCredentialStatus.CONFIGURED

    blocking_reason: str | None = None
    if not mode_supported:
        blocking_reason = (
            "Configured embedding provider mode is not supported by the current provider backbone."
        )
    elif not live_mode_requested:
        blocking_reason = "Live embedding execution is not currently requested by runtime mode."
    elif not configuration.configuration_valid:
        blocking_reason = (
            "Live embedding provider configuration is invalid and cannot be activated safely."
        )
    elif not credentials_configured:
        blocking_reason = "Live embedding provider credentials are not fully configured."

    return EmbeddingLiveExecutionState(
        provider_mode=resolve_runtime_mode_config().embedding_provider_mode,
        configuration_valid=configuration.configuration_valid,
        credentials_configured=credentials_configured,
        mode_supported=mode_supported,
        live_mode_requested=live_mode_requested,
        live_execution_enabled=blocking_reason is None,
        configured_provider_id=configuration.configured_live_provider_id,
        configured_model_id=configuration.configured_live_model_id,
        blocking_reason=blocking_reason,
    )
