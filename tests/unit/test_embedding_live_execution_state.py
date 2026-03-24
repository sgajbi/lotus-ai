from app.config import settings
from app.services.embedding_live_execution_state import build_embedding_live_execution_state


def test_embedding_live_execution_state_defaults_to_blocked() -> None:
    state = build_embedding_live_execution_state()

    assert state.live_execution_enabled is False
    assert state.live_mode_requested is False
    assert state.blocking_reason is not None


def test_embedding_live_execution_state_reports_enabled_when_configured() -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    state = build_embedding_live_execution_state()

    assert state.live_execution_enabled is True
    assert state.live_mode_requested is True
    assert state.configured_provider_id == "embeddings.openai"
