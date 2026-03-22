from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderConfigurationStatusDescriptor,
    ProviderCredentialStatus,
    ProviderRolloutState,
)
from app.services.provider_task_allowlist import (
    list_invalid_live_text_allowlisted_task_ids,
    list_live_text_allowlisted_task_ids,
)


def build_text_generation_configuration_status() -> ProviderConfigurationStatusDescriptor:
    rollout_state = _resolve_rollout_state()
    configured_live_provider_id = settings.live_text_provider_id
    configured_live_model_id = settings.live_text_model_id
    api_key = settings.live_text_provider_api_key
    allowlisted_task_ids = list_live_text_allowlisted_task_ids()
    invalid_allowlisted_task_ids = list_invalid_live_text_allowlisted_task_ids()

    findings: list[str] = []
    configuration_valid = True

    if rollout_state is None:
        configuration_valid = False
        findings.append(
            "Configured provider rollout state is not recognized and cannot be evaluated safely."
        )

    rollout_requires_live_config = rollout_state in {
        ProviderRolloutState.ALLOWLISTED_DISABLED,
        ProviderRolloutState.CANARY_ENABLED,
        ProviderRolloutState.ROLLED_OUT,
    }
    live_config_values = [
        configured_live_provider_id,
        configured_live_model_id,
        api_key,
    ]
    populated_live_config_count = sum(bool(value) for value in live_config_values)

    if rollout_requires_live_config and populated_live_config_count < len(live_config_values):
        configuration_valid = False
        findings.append(
            "Live-provider rollout state requires allowlisted provider id, model id, and provider credential configuration."
        )
    if rollout_requires_live_config and not allowlisted_task_ids:
        configuration_valid = False
        findings.append(
            "Live-provider rollout state requires at least one allowlisted task id for bounded activation."
        )
    if invalid_allowlisted_task_ids:
        configuration_valid = False
        findings.append(
            "Live-provider task allowlist contains unknown or retrieval-backed task ids, which are not valid for live text-generation rollout."
        )
    if configured_live_provider_id not in {None, "text.openai"}:
        configuration_valid = False
        findings.append(
            "Configured live text provider id is not recognized by the current provider backbone."
        )

    if not rollout_requires_live_config and populated_live_config_count > 0:
        findings.append(
            "Live-provider configuration values are present, but rollout remains below live activation posture."
        )

    if populated_live_config_count == 0:
        credential_status = ProviderCredentialStatus.NOT_CONFIGURED
    elif populated_live_config_count == len(live_config_values):
        credential_status = ProviderCredentialStatus.CONFIGURED
    else:
        credential_status = ProviderCredentialStatus.INVALID
        configuration_valid = False
        findings.append(
            "Live-provider credentials or allowlist configuration are partially populated and therefore invalid."
        )

    if rollout_state is None:
        resolved_rollout_state = ProviderRolloutState.DOCUMENTED_ONLY
    else:
        resolved_rollout_state = rollout_state

    if not findings:
        findings.append(
            "Provider rollout posture is internally consistent for the current foundation phase."
        )

    return ProviderConfigurationStatusDescriptor(
        rollout_state=resolved_rollout_state,
        configured_live_provider_id=configured_live_provider_id,
        configured_live_model_id=configured_live_model_id,
        allowlisted_task_ids=allowlisted_task_ids,
        credential_status=credential_status,
        configuration_valid=configuration_valid,
        findings=findings,
    )


def _resolve_rollout_state() -> ProviderRolloutState | None:
    configured_state = settings.provider_rollout_state
    try:
        return ProviderRolloutState(configured_state)
    except ValueError:
        return None
