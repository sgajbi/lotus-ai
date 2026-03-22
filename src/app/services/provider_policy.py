from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.providers import (
    ProviderCapability,
    ProviderExecutionMode,
    ProviderPolicyDescriptor,
    ProviderPolicyResponse,
)


def build_provider_policy() -> ProviderPolicyResponse:
    return ProviderPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        policies=[
            ProviderPolicyDescriptor(
                capability=ProviderCapability.TEXT_GENERATION,
                configured_mode=settings.provider_mode,
                allowed_modes=[
                    ProviderExecutionMode.DISABLED,
                    ProviderExecutionMode.STUB,
                ],
                selected_provider_id=_selected_text_provider_id(),
                live_execution_enabled=False,
                rejection_behavior=(
                    "Reject unsupported provider modes with HTTP 503 until a governed live "
                    "provider rollout is approved."
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
                live_execution_enabled=False,
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


def _selected_text_provider_id() -> str:
    return "text.stub"
