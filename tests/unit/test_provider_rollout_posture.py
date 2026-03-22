from app.config import settings
from app.contracts.providers import ProviderRolloutState
from app.services.provider_rollout_posture import build_provider_rollout_posture


def test_provider_rollout_posture_reports_stub_default_path() -> None:
    posture = build_provider_rollout_posture()

    assert posture.rollout_state == ProviderRolloutState.STUB_DEFAULT
    assert posture.configuration_valid is True
    assert posture.live_path_configured is False
    assert "stub path" in posture.notes


def test_provider_rollout_posture_reports_allowlisted_disabled_live_path() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-4.1-mini"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    posture = build_provider_rollout_posture()

    assert posture.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED
    assert posture.configuration_valid is True
    assert posture.live_path_configured is True
    assert "allowlisted" in posture.notes


def test_provider_rollout_posture_reports_canary_enabled_live_path() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-4.1-mini"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    posture = build_provider_rollout_posture()

    assert posture.rollout_state == ProviderRolloutState.CANARY_ENABLED
    assert posture.configuration_valid is True
    assert "canary posture" in posture.notes


def test_provider_rollout_posture_reports_documented_only_state() -> None:
    settings.provider_rollout_state = "DOCUMENTED_ONLY"

    posture = build_provider_rollout_posture()

    assert posture.rollout_state == ProviderRolloutState.DOCUMENTED_ONLY
    assert "documented" in posture.notes


def test_provider_rollout_posture_reports_rolled_out_state() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "ROLLED_OUT"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-4.1-mini"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    posture = build_provider_rollout_posture()

    assert posture.rollout_state == ProviderRolloutState.ROLLED_OUT
    assert "rolled out" in posture.notes
