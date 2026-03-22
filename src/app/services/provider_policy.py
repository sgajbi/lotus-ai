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
from app.providers.registry import resolve_text_generation_adapter
from app.services.provider_configuration_status import (
    build_text_generation_configuration_status,
)
from app.services.provider_live_execution_state import build_provider_live_execution_state


def build_provider_policy() -> ProviderPolicyResponse:
    selected_text_provider = _resolve_selected_text_provider()
    live_execution_state = build_provider_live_execution_state()
    if settings.provider_mode == ProviderExecutionMode.OPENAI.value:
        rejection_category = ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
    else:
        rejection_category = ProviderFailureCategory.UNSUPPORTED_MODE
    return ProviderPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        text_generation_configuration=build_text_generation_configuration_status(),
        policies=[
            ProviderPolicyDescriptor(
                capability=ProviderCapability.TEXT_GENERATION,
                configured_mode=settings.provider_mode,
                allowed_modes=[
                    ProviderExecutionMode.DISABLED,
                    ProviderExecutionMode.STUB,
                    ProviderExecutionMode.OPENAI,
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
                ],
                selected_provider_id="embeddings.stub",
                selected_adapter_kind=ProviderAdapterKind.STUB,
                live_execution_enabled=False,
                rejection_category=ProviderFailureCategory.UNSUPPORTED_MODE,
                rejection_behavior=(
                    "Reject unsupported embedding provider modes with HTTP 503 until retrieval "
                    "execution is enabled."
                ),
            ),
        ],
    )


def require_supported_text_generation_mode() -> ProviderExecutionMode:
    supported_modes = {mode.value: mode for mode in ProviderExecutionMode}
    configured_mode = settings.provider_mode
    if configured_mode not in supported_modes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Configured text-generation provider mode is not supported in the current phase: "
                f"{configured_mode}"
            ),
        )
    return supported_modes[configured_mode]


def _resolve_selected_text_provider() -> tuple[str, ProviderAdapterKind]:
    configured_mode = settings.provider_mode
    if configured_mode not in {mode.value for mode in ProviderExecutionMode}:
        return ("text.unresolved", ProviderAdapterKind.OPENAI_LIVE)
    adapter = resolve_text_generation_adapter(ProviderExecutionMode(configured_mode))
    return (adapter.descriptor.provider_id, adapter.descriptor.adapter_kind)
