from __future__ import annotations

from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.providers import (
    ProviderCapability,
    ProviderConfigurationStatusDescriptor,
    ProviderCredentialStatus,
    ProviderExecutionMode,
    ProviderRolloutState,
)
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.provider_task_allowlist import (
    list_invalid_live_text_allowlisted_task_ids,
    list_live_text_allowlisted_task_ids,
)


def build_text_generation_configuration_status() -> ProviderConfigurationStatusDescriptor:
    config = resolve_provider_execution_config()
    rollout_state = _resolve_rollout_state()
    configured_live_provider_id = config.provider_id
    configured_live_model_id = config.model_id
    api_key = config.api_key
    api_base = config.api_base
    provider_mode = config.provider_mode
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
    expected_provider_ids = _expected_live_text_provider_ids(provider_mode)
    api_key_required = _live_text_api_key_required(provider_mode)
    live_config_values = [configured_live_provider_id, configured_live_model_id]
    if api_key_required:
        live_config_values.append(api_key)
    populated_live_config_count = sum(bool(value) for value in live_config_values)

    if rollout_requires_live_config and populated_live_config_count < len(live_config_values):
        configuration_valid = False
        findings.append(
            "Live-provider rollout state requires allowlisted provider id, model id, and any mandatory credential configuration."
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
    if configured_live_provider_id not in expected_provider_ids:
        configuration_valid = False
        findings.append(
            "Configured live text provider id is not recognized by the current provider backbone."
        )
    if provider_mode == ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value and (
        api_base.strip().rstrip("/") == "https://api.openai.com/v1"
    ):
        configuration_valid = False
        findings.append(
            "Local OpenAI-compatible mode requires a non-default local or self-hosted API base."
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
        capability=ProviderCapability.TEXT_GENERATION,
        rollout_state=resolved_rollout_state,
        configured_live_provider_id=configured_live_provider_id,
        configured_live_model_id=configured_live_model_id,
        allowlisted_task_ids=allowlisted_task_ids,
        credential_status=credential_status,
        configuration_valid=configuration_valid,
        findings=findings,
    )


def build_embedding_configuration_status() -> ProviderConfigurationStatusDescriptor:
    configured_mode = resolve_runtime_mode_config().embedding_provider_mode
    configured_live_provider_id = resolve_runtime_mode_config().embedding_provider_id
    configured_live_model_id = resolve_runtime_mode_config().embedding_model_id
    api_key = resolve_runtime_mode_config().embedding_api_key
    findings: list[str] = []
    configuration_valid = True
    allowlisted_task_ids: list[str] = []

    if configured_mode == ProviderExecutionMode.DISABLED.value:
        rollout_state = ProviderRolloutState.DOCUMENTED_ONLY
        credential_status = ProviderCredentialStatus.NOT_CONFIGURED
        findings.append(
            "Embedding provider rollout remains documented-only until a later RFC-0018 slice enables governed live execution."
        )
    elif configured_mode == ProviderExecutionMode.STUB.value:
        rollout_state = ProviderRolloutState.STUB_DEFAULT
        credential_status = ProviderCredentialStatus.NOT_CONFIGURED
        findings.append(
            "Embedding provider remains on the stub path for contract validation and bounded retrieval preparation."
        )
    elif configured_mode == ProviderExecutionMode.ENABLED.value:
        rollout_state = ProviderRolloutState.CANARY_ENABLED
        live_config_values = [
            configured_live_provider_id,
            configured_live_model_id,
            api_key,
        ]
        populated_live_config_count = sum(bool(value) for value in live_config_values)
        if configured_live_provider_id not in {None, "embeddings.openai"}:
            configuration_valid = False
            findings.append(
                "Configured live embedding provider id is not recognized by the current provider backbone."
            )
        if populated_live_config_count == 0:
            credential_status = ProviderCredentialStatus.NOT_CONFIGURED
            configuration_valid = False
            findings.append(
                "Live embedding mode requires configured provider id, model id, and provider credential values."
            )
        elif populated_live_config_count == len(live_config_values):
            credential_status = ProviderCredentialStatus.CONFIGURED
        else:
            credential_status = ProviderCredentialStatus.INVALID
            configuration_valid = False
            findings.append(
                "Live embedding credentials are partially populated and therefore invalid."
            )
        findings.append(
            "Live embedding provider execution is now configured for bounded rollout, but broader retrieval/provider governance still remains a separate approval concern."
        )
    else:
        rollout_state = ProviderRolloutState.DOCUMENTED_ONLY
        credential_status = ProviderCredentialStatus.INVALID
        configuration_valid = False
        findings.append(
            "Configured embedding provider mode is not recognized and cannot be evaluated safely."
        )

    return ProviderConfigurationStatusDescriptor(
        capability=ProviderCapability.EMBEDDINGS,
        rollout_state=rollout_state,
        configured_live_provider_id=configured_live_provider_id,
        configured_live_model_id=configured_live_model_id,
        allowlisted_task_ids=allowlisted_task_ids,
        credential_status=credential_status,
        configuration_valid=configuration_valid,
        findings=findings,
    )


def _resolve_rollout_state() -> ProviderRolloutState | None:
    configured_state = resolve_provider_execution_config().rollout_state
    try:
        return ProviderRolloutState(configured_state)
    except ValueError:
        return None


def _expected_live_text_provider_ids(provider_mode: str) -> set[str | None]:
    if provider_mode == ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value:
        return {None, "text.local"}
    return {None, "text.openai"}


def _live_text_api_key_required(provider_mode: str) -> bool:
    return provider_mode != ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value
