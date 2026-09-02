from __future__ import annotations

from app.config import settings
from app.contracts.provider_catalog import (
    ProviderOperatorProfileDescriptor,
    ProviderOperatorProfileResponse,
)
from app.contracts.providers import ProviderExecutionMode
from app.services.provider_live_execution_state import (
    ProviderLiveExecutionState,
    build_provider_live_execution_state,
)


def build_provider_operator_profile() -> ProviderOperatorProfileResponse:
    live_execution_state = build_provider_live_execution_state(task_id="explain.v1")
    selected_profile_id = _resolve_selected_profile_id()
    profiles = _build_profiles()

    return ProviderOperatorProfileResponse(
        service=settings.service_name,
        version=settings.service_version,
        selected_profile_id=selected_profile_id,
        provider_mode=settings.provider_mode,
        current_provider_id=settings.live_text_provider_id,
        current_model_id=settings.live_text_model_id,
        live_execution_enabled=live_execution_state.live_execution_enabled,
        current_readiness_note=_build_current_readiness_note(
            selected_profile_id=selected_profile_id,
            live_execution_state=live_execution_state,
        ),
        switching_steps=[
            "Set the target provider mode and its required live text settings in `.env`.",
            "Recreate `lotus-ai` and `lotus-ai-worker` so runtime mode changes take effect cleanly.",
            "If using a local model server, start the matching Docker profile and ensure the configured model is loaded before expecting live execution.",
            "Verify `/platform/providers/operator-profile`, `/platform/providers`, `/platform/providers/policy`, and `/platform/providers/operations-status` agree on the active provider posture.",
            "Run one bounded `POST /ai/tasks/execute` request and confirm `audit.provider_mode`, `provider_id`, and `stubbed` match the intended profile.",
        ],
        profiles=profiles,
    )


def _build_profiles() -> list[ProviderOperatorProfileDescriptor]:
    verification_surfaces = [
        "/platform/providers/operator-profile",
        "/platform/providers",
        "/platform/providers/policy",
        "/platform/providers/operations-status",
        "/platform/providers/activation-readiness",
        "/ai/tasks/execute",
    ]
    return [
        ProviderOperatorProfileDescriptor(
            profile_id="stubbed_disabled",
            display_name="Deterministic Stub",
            provider_mode=ProviderExecutionMode.DISABLED.value,
            provider_id="text.stub",
            api_base_class="none",
            docker_profile=None,
            use_case="Billing-off, deterministic platform validation and fallback execution.",
            required_settings=["LOTUS_AI_PROVIDER_MODE"],
            verification_surfaces=verification_surfaces,
        ),
        ProviderOperatorProfileDescriptor(
            profile_id="managed_openai",
            display_name="Managed OpenAI",
            provider_mode=ProviderExecutionMode.OPENAI.value,
            provider_id="text.openai",
            api_base_class="managed_openai",
            docker_profile=None,
            use_case="Managed remote execution when approved external provider billing and quota posture are acceptable.",
            required_settings=[
                "LOTUS_AI_PROVIDER_MODE",
                "LOTUS_AI_PROVIDER_ROLLOUT_STATE",
                "LOTUS_AI_LIVE_TEXT_PROVIDER_ID",
                "LOTUS_AI_LIVE_TEXT_MODEL_ID",
                "LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY",
                "LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS",
            ],
            verification_surfaces=verification_surfaces,
        ),
        ProviderOperatorProfileDescriptor(
            profile_id="local_ollama",
            display_name="Local OpenAI-Compatible via Ollama",
            provider_mode=ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
            provider_id="text.local",
            api_base_class="local_openai_compatible",
            docker_profile="local-llm",
            use_case="Developer-local or workstation-local execution with a smaller governed model and no managed-provider billing.",
            required_settings=[
                "LOTUS_AI_PROVIDER_MODE",
                "LOTUS_AI_PROVIDER_ROLLOUT_STATE",
                "LOTUS_AI_LIVE_TEXT_PROVIDER_ID",
                "LOTUS_AI_LIVE_TEXT_MODEL_ID",
                "LOTUS_AI_LIVE_TEXT_API_BASE",
                "LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS",
            ],
            verification_surfaces=verification_surfaces,
        ),
        ProviderOperatorProfileDescriptor(
            profile_id="local_vllm",
            display_name="Local OpenAI-Compatible via vLLM",
            provider_mode=ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
            provider_id="text.local",
            api_base_class="local_openai_compatible",
            docker_profile=None,
            use_case="Shared-host or stronger workstation deployment when higher local throughput is needed behind the same bounded task contract.",
            required_settings=[
                "LOTUS_AI_PROVIDER_MODE",
                "LOTUS_AI_PROVIDER_ROLLOUT_STATE",
                "LOTUS_AI_LIVE_TEXT_PROVIDER_ID",
                "LOTUS_AI_LIVE_TEXT_MODEL_ID",
                "LOTUS_AI_LIVE_TEXT_API_BASE",
                "LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS",
            ],
            verification_surfaces=verification_surfaces,
        ),
    ]


def _resolve_selected_profile_id() -> str:
    if settings.provider_mode == ProviderExecutionMode.DISABLED.value:
        return "stubbed_disabled"
    if settings.provider_mode == ProviderExecutionMode.OPENAI.value:
        return "managed_openai"
    if settings.provider_mode == ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value:
        api_base = settings.live_text_api_base.lower()
        if "ollama" in api_base:
            return "local_ollama"
        return "local_vllm"
    return "stubbed_disabled"


def _build_current_readiness_note(
    *,
    selected_profile_id: str,
    live_execution_state: ProviderLiveExecutionState,
) -> str:
    if live_execution_state.live_execution_enabled:
        if selected_profile_id.startswith("local_"):
            return (
                "Local OpenAI-compatible execution is active and the configured model is currently "
                "advertised by the local endpoint."
            )
        if selected_profile_id == "managed_openai":
            return "Managed OpenAI execution is active for the configured allowlisted task path."
        return "Deterministic stub execution is active."
    if live_execution_state.blocking_reason is not None:
        return str(live_execution_state.blocking_reason)
    return "Provider posture is configured but not yet active."
