from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.providers import (
    ProviderCredentialStatus,
    ProviderExecutionMode,
    ProviderRolloutState,
)
from app.services.provider_configuration_status import build_text_generation_configuration_status
from app.services.provider_task_allowlist import is_live_text_task_allowlisted


@dataclass(frozen=True)
class ProviderLiveExecutionState:
    provider_mode: str
    rollout_state: ProviderRolloutState
    configuration_valid: bool
    credentials_configured: bool
    mode_supported: bool
    live_mode_requested: bool
    live_execution_enabled: bool
    task_allowlisted: bool
    blocking_reason: str | None


def build_provider_live_execution_state(
    *, task_id: str | None = None
) -> ProviderLiveExecutionState:
    configuration = build_text_generation_configuration_status()
    mode_supported = settings.provider_mode in {
        ProviderExecutionMode.DISABLED.value,
        ProviderExecutionMode.STUB.value,
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }
    live_mode_requested = settings.provider_mode in {
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }
    credentials_configured = configuration.credential_status == ProviderCredentialStatus.CONFIGURED
    rollout_permits_live_execution = configuration.rollout_state in {
        ProviderRolloutState.CANARY_ENABLED,
        ProviderRolloutState.ROLLED_OUT,
    }
    task_allowlisted = task_id is None or is_live_text_task_allowlisted(task_id)

    blocking_reason: str | None = None
    if not mode_supported:
        blocking_reason = (
            "Configured provider mode is not supported by the current provider backbone."
        )
    elif not live_mode_requested:
        blocking_reason = "Live provider execution is not currently requested by runtime mode."
    elif not configuration.configuration_valid:
        blocking_reason = "Live provider configuration is invalid and cannot be activated safely."
    elif not credentials_configured:
        blocking_reason = "Live provider credentials are not fully configured."
    elif not rollout_permits_live_execution:
        blocking_reason = "Live provider rollout posture does not yet permit active execution."
    elif not task_allowlisted:
        blocking_reason = f"Task '{task_id}' is not allowlisted for live text-generation execution."

    return ProviderLiveExecutionState(
        provider_mode=settings.provider_mode,
        rollout_state=configuration.rollout_state,
        configuration_valid=configuration.configuration_valid,
        credentials_configured=credentials_configured,
        mode_supported=mode_supported,
        live_mode_requested=live_mode_requested,
        live_execution_enabled=blocking_reason is None,
        task_allowlisted=task_allowlisted,
        blocking_reason=blocking_reason,
    )
