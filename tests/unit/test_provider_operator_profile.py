from __future__ import annotations

from pytest import MonkeyPatch

from app.config import settings
from app.services.provider_operator_profile import build_provider_operator_profile


def test_provider_operator_profile_reports_disabled_stub_profile() -> None:
    profile = build_provider_operator_profile()

    assert profile.selected_profile_id == "stubbed_disabled"
    assert profile.provider_mode == "disabled"
    assert profile.live_execution_enabled is False
    assert any(item.profile_id == "managed_openai" for item in profile.profiles)
    assert any(item.profile_id == "local_ollama" for item in profile.profiles)


def test_provider_operator_profile_reports_local_ollama_profile_when_selected(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
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

    profile = build_provider_operator_profile()

    assert profile.selected_profile_id == "local_ollama"
    assert profile.provider_mode == "local_openai_compatible"
    assert profile.live_execution_enabled is True
    assert "local endpoint" in profile.current_readiness_note.lower()
    assert "/ai/tasks/execute" in profile.switching_steps[-1]


def test_provider_operator_profile_reports_managed_openai_profile_when_selected(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "openai"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    monkeypatch.setattr(
        "app.services.provider_operator_profile.build_provider_live_execution_state",
        lambda task_id: type(
            "LiveExecutionState",
            (),
            {
                "live_execution_enabled": True,
                "blocking_reason": None,
            },
        )(),
    )

    profile = build_provider_operator_profile()

    assert profile.selected_profile_id == "managed_openai"
    assert profile.current_provider_id == "text.openai"
    assert "managed openai execution is active" in profile.current_readiness_note.lower()


def test_provider_operator_profile_reports_local_vllm_profile_when_api_base_is_not_ollama(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://vllm:8000/v1"
    monkeypatch.setattr(
        "app.services.provider_operator_profile.build_provider_live_execution_state",
        lambda task_id: type(
            "LiveExecutionState",
            (),
            {
                "live_execution_enabled": False,
                "blocking_reason": None,
            },
        )(),
    )

    profile = build_provider_operator_profile()

    assert profile.selected_profile_id == "local_vllm"
    assert profile.current_readiness_note == "Provider posture is configured but not yet active."


def test_provider_operator_profile_surfaces_runtime_blocking_reason(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.provider_operator_profile.build_provider_live_execution_state",
        lambda task_id: type(
            "LiveExecutionState",
            (),
            {
                "live_execution_enabled": False,
                "blocking_reason": "Configured model is not available.",
            },
        )(),
    )

    profile = build_provider_operator_profile()

    assert profile.current_readiness_note == "Configured model is not available."
