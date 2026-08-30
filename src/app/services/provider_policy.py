from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
    ProviderFailureCategory,
    ProviderPolicyDescriptor,
    ProviderPolicyResponse,
)
from app.providers.registry import resolve_embedding_adapter, resolve_text_generation_adapter
from app.services.embedding_live_execution_state import build_embedding_live_execution_state
from app.services.provider_expansion_policy import build_provider_expansion_policy
from app.services.provider_configuration_status import (
    build_embedding_configuration_status,
    build_text_generation_configuration_status,
)
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.provider_live_execution_state import build_provider_live_execution_state


def build_provider_policy() -> ProviderPolicyResponse:
    text_mode = resolve_provider_execution_config().provider_mode
    selected_text_provider = _resolve_selected_text_provider()
    selected_embedding_provider = _resolve_selected_embedding_provider()
    live_execution_state = build_provider_live_execution_state()
    embedding_live_execution_state = build_embedding_live_execution_state()
    if text_mode == ProviderExecutionMode.OPENAI.value:
        rejection_category = ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
    elif text_mode == ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value:
        rejection_category = ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
    else:
        rejection_category = ProviderFailureCategory.UNSUPPORTED_MODE
    if settings.embedding_provider_mode == ProviderExecutionMode.ENABLED.value:
        embedding_rejection_category = ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
    else:
        embedding_rejection_category = ProviderFailureCategory.UNSUPPORTED_MODE
    return ProviderPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        text_generation_configuration=build_text_generation_configuration_status(),
        embedding_configuration=build_embedding_configuration_status(),
        expansion_policy=build_provider_expansion_policy(),
        policies=[
            ProviderPolicyDescriptor(
                capability=ProviderCapability.TEXT_GENERATION,
                configured_mode=text_mode,
                allowed_modes=[
                    ProviderExecutionMode.DISABLED,
                    ProviderExecutionMode.STUB,
                    ProviderExecutionMode.OPENAI,
                    ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE,
                ],
                selected_provider_id=selected_text_provider[0],
                selected_adapter_kind=selected_text_provider[1],
                live_execution_enabled=live_execution_state.live_execution_enabled,
                rejection_category=rejection_category,
                rejection_behavior=(
                    "Reject unsupported provider modes, blocked live rollout states, and "
                    "non-allowlisted tasks with HTTP 503 until governed live execution is approved."
                ),
            ),
            ProviderPolicyDescriptor(
                capability=ProviderCapability.EMBEDDINGS,
                configured_mode=settings.embedding_provider_mode,
                allowed_modes=[
                    ProviderExecutionMode.DISABLED,
                    ProviderExecutionMode.STUB,
                    ProviderExecutionMode.ENABLED,
                ],
                selected_provider_id=selected_embedding_provider[0],
                selected_adapter_kind=selected_embedding_provider[1],
                live_execution_enabled=embedding_live_execution_state.live_execution_enabled,
                rejection_category=embedding_rejection_category,
                rejection_behavior=(
                    "Reject unsupported embedding provider modes, incomplete live embedding "
                    "configuration, and pre-activation live embedding requests with HTTP 503 "
                    "until governed retrieval and provider rollout is approved."
                ),
            ),
        ],
    )


def require_supported_text_generation_mode() -> ProviderExecutionMode:
    supported_modes = {
        ProviderExecutionMode.DISABLED.value: ProviderExecutionMode.DISABLED,
        ProviderExecutionMode.STUB.value: ProviderExecutionMode.STUB,
        ProviderExecutionMode.OPENAI.value: ProviderExecutionMode.OPENAI,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value: ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE,
    }
    configured_mode = resolve_provider_execution_config().provider_mode
    if configured_mode not in supported_modes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Configured text-generation provider mode is not supported in the current phase: "
                f"{configured_mode}"
            ),
        )
    return supported_modes[configured_mode]


def require_supported_embedding_mode() -> ProviderExecutionMode:
    supported_modes = {
        ProviderExecutionMode.DISABLED.value: ProviderExecutionMode.DISABLED,
        ProviderExecutionMode.STUB.value: ProviderExecutionMode.STUB,
        ProviderExecutionMode.ENABLED.value: ProviderExecutionMode.ENABLED,
    }
    configured_mode = settings.embedding_provider_mode
    if configured_mode not in supported_modes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Configured embedding provider mode is not supported in the current phase: "
                f"{configured_mode}"
            ),
        )
    return supported_modes[configured_mode]


def _resolve_selected_text_provider() -> tuple[str, ProviderAdapterKind]:
    configured_mode = resolve_provider_execution_config().provider_mode
    if configured_mode not in {
        ProviderExecutionMode.DISABLED.value,
        ProviderExecutionMode.STUB.value,
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }:
        return ("text.unresolved", ProviderAdapterKind.OPENAI_LIVE)
    adapter = resolve_text_generation_adapter(ProviderExecutionMode(configured_mode))
    return (adapter.descriptor.provider_id, adapter.descriptor.adapter_kind)


def _resolve_selected_embedding_provider() -> tuple[str, ProviderAdapterKind]:
    configured_mode = settings.embedding_provider_mode
    supported_modes = {
        ProviderExecutionMode.DISABLED.value,
        ProviderExecutionMode.STUB.value,
        ProviderExecutionMode.ENABLED.value,
    }
    if configured_mode not in supported_modes:
        return ("embeddings.unresolved", ProviderAdapterKind.OPENAI_EMBEDDINGS_LIVE)
    adapter = resolve_embedding_adapter(ProviderExecutionMode(configured_mode))
    return (adapter.descriptor.provider_id, adapter.descriptor.adapter_kind)
