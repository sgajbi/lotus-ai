import json
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from app.config import settings
from app.contracts.providers import EmbeddingExecutionRequest
from app.providers.base import ProviderExecutionError
from app.services.embedding_provider_gateway import execute_embedding_generation


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        return None


def test_execute_embedding_generation_uses_stub_path_by_default() -> None:
    response = execute_embedding_generation(
        EmbeddingExecutionRequest(
            caller_app="lotus-platform",
            corpus_id="lotus-platform-rfcs",
            content="Governed retrieval indexing remains bounded.",
        )
    )

    assert response.provider_id == "embeddings.stub"
    assert response.stubbed is True
    assert response.vector_dimension == len(response.embedding)


def test_execute_embedding_generation_uses_live_openai_path_when_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    monkeypatch.setattr(
        "app.providers.openai_live_embedding_provider.urllib_request.urlopen",
        lambda request, timeout: _FakeResponse(
            {
                "object": "list",
                "model": "text-embedding-3-large",
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
            }
        ),
    )

    response = execute_embedding_generation(
        EmbeddingExecutionRequest(
            caller_app="lotus-platform",
            corpus_id="lotus-platform-rfcs",
            content="Governed retrieval indexing remains bounded.",
        )
    )

    assert response.provider_id == "embeddings.openai"
    assert response.stubbed is False
    assert response.vector_dimension == 3


def test_execute_embedding_generation_rejects_invalid_live_configuration() -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"

    try:
        execute_embedding_generation(
            EmbeddingExecutionRequest(
                caller_app="lotus-platform",
                corpus_id="lotus-platform-rfcs",
                content="Governed retrieval indexing remains bounded.",
            )
        )
    except ProviderExecutionError as exc:
        assert exc.category.value == "LIVE_EXECUTION_NOT_ENABLED"
        assert "invalid" in exc.message.lower()
    else:
        raise AssertionError("Expected invalid live embedding configuration to be rejected")
