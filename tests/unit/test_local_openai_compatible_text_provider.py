from pytest import MonkeyPatch

from app.config import settings
from app.providers.local_openai_compatible_text_provider import (
    LocalOpenAICompatibleTextProvider,
)
from tests.unit.test_provider_gateway import _request


def test_local_openai_compatible_text_provider_returns_usage_without_api_key(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_provider_api_key = None
    settings.live_text_input_cost_per_1k_tokens = 0.0
    settings.live_text_output_cost_per_1k_tokens = 0.0

    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_local_123",
            "model": "qwen3:8b",
            "output_text": "Local provider explanation.",
            "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        },
    )

    response = LocalOpenAICompatibleTextProvider().execute(_request())

    assert response.provider_id == "text.local"
    assert response.provider_mode == "local_openai_compatible"
    assert response.stubbed is False
    assert response.model_id == "qwen3:8b"
    assert response.provider_request_id == "resp_local_123"
    assert response.input_tokens == 120
    assert response.output_tokens == 40
    assert response.total_tokens == 160
    assert response.message == "Local provider explanation."
