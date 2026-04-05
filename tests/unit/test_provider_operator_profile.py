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
