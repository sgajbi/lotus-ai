from __future__ import annotations

from pytest import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderRolloutState
from app.services.provider_live_execution_state import build_provider_live_execution_state


def test_provider_live_execution_state_reports_disabled_default_mode() -> None:
    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.provider_mode == "disabled"
    assert state.rollout_state == ProviderRolloutState.STUB_DEFAULT
    assert state.live_mode_requested is False
    assert state.live_execution_enabled is False
    assert (
        state.blocking_reason
        == "Live provider execution is not currently requested by runtime mode."
    )


def test_provider_live_execution_state_allows_configured_canary_task() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.live_mode_requested is True
    assert state.credentials_configured is True
    assert state.task_allowlisted is True
    assert state.live_execution_enabled is True
    assert state.blocking_reason is None


def test_provider_live_execution_state_allows_local_openai_compatible_task_without_api_key(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_provider_api_key = None
    settings.live_text_allowed_task_ids = "explain.v1"
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {
                "endpoint_reachable": True,
                "model_available": True,
                "blocking_reason": None,
            },
        )(),
    )

    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.live_mode_requested is True
    assert state.credentials_configured is True
    assert state.task_allowlisted is True
    assert state.live_execution_enabled is True
    assert state.endpoint_reachable is True
    assert state.configured_model_available is True
    assert state.blocking_reason is None


def test_provider_live_execution_state_blocks_local_mode_when_endpoint_is_unreachable(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_provider_api_key = None
    settings.live_text_allowed_task_ids = "explain.v1"
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {
                "endpoint_reachable": False,
                "model_available": False,
                "blocking_reason": "Local OpenAI-compatible endpoint is not reachable.",
            },
        )(),
    )

    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.live_execution_enabled is False
    assert state.endpoint_reachable is False
    assert state.configured_model_available is False
    assert "not reachable" in (state.blocking_reason or "")


def test_provider_live_execution_state_blocks_non_allowlisted_task() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "summarize.v1"

    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.live_execution_enabled is False
    assert state.task_allowlisted is False
    assert "not allowlisted" in (state.blocking_reason or "")


def test_provider_live_execution_state_rejects_unsupported_mode() -> None:
    settings.provider_mode = "unsupported"

    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.mode_supported is False
    assert state.live_execution_enabled is False
    assert "not supported" in (state.blocking_reason or "")


def test_provider_live_execution_state_rejects_invalid_configuration() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "knowledge_answer.v1"

    state = build_provider_live_execution_state(task_id="explain.v1")

    assert state.configuration_valid is False
    assert state.live_execution_enabled is False
    assert "invalid" in (state.blocking_reason or "")
