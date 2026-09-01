from email.message import Message
from io import BytesIO
from urllib import error

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.providers import EmbeddingExecutionRequest, ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.providers.openai_live_embedding_provider import (
    OpenAILiveEmbeddingProvider,
    _as_str,
    _extract_embedding,
    _load_error_payload,
    _post_openai_embedding,
)


def _request() -> EmbeddingExecutionRequest:
    return EmbeddingExecutionRequest(
        caller_app="lotus-platform",
        corpus_id="lotus-platform-rfcs",
        content="Governed retrieval indexing remains bounded.",
    )


def test_openai_live_embedding_provider_returns_vector_metadata(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    monkeypatch.setattr(
        "app.providers.openai_live_embedding_provider._post_openai_embedding",
        lambda **_: {
            "model": "text-embedding-3-large",
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
        },
    )

    response = OpenAILiveEmbeddingProvider().embed(_request())

    assert response.provider_id == "embeddings.openai"
    assert response.provider_mode == "enabled"
    assert response.stubbed is False
    assert response.model_id == "text-embedding-3-large"
    assert response.vector_dimension == 3
    assert response.embedding == [0.1, 0.2, 0.3]


def test_openai_live_embedding_provider_requires_api_key() -> None:
    settings.live_embedding_provider_api_key = None

    try:
        OpenAILiveEmbeddingProvider().embed(_request())
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.INVALID_LIVE_CONFIGURATION
    else:
        raise AssertionError("Expected ProviderExecutionError for missing embedding credentials")


def test_openai_live_embedding_provider_maps_rate_limit_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    def _raise_http_error(*args: object, **kwargs: object) -> object:
        raise error.HTTPError(
            url="https://api.openai.com/v1/embeddings",
            code=429,
            msg="Too Many Requests",
            hdrs=Message(),
            fp=BytesIO(b'{"error": {"message": "Embedding rate limit hit"}}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    try:
        _post_openai_embedding(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "text-embedding-3-large", "input": "hello"},
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_RATE_LIMITED
        assert exc.message == "embeddings.openai rate limit exceeded."
        assert "Embedding rate limit hit" not in exc.message
    else:
        raise AssertionError("Expected rate-limited embedding request to fail")


def test_openai_live_embedding_provider_maps_upstream_http_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    def _raise_http_error(*args: object, **kwargs: object) -> object:
        raise error.HTTPError(
            url="https://api.openai.com/v1/embeddings",
            code=500,
            msg="Server Error",
            hdrs=Message(),
            fp=BytesIO(b"not json"),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    try:
        _post_openai_embedding(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "text-embedding-3-large", "input": "hello"},
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
        assert exc.message == (
            "embeddings.openai request failed at the upstream provider boundary."
        )
    else:
        raise AssertionError("Expected upstream embedding request to fail")


def test_openai_live_embedding_provider_maps_timeout_errors(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()),
    )

    try:
        _post_openai_embedding(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "text-embedding-3-large", "input": "hello"},
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT
        assert exc.message == (
            "embeddings.openai request did not complete within the configured timeout."
        )
    else:
        raise AssertionError("Expected timeout embedding request to fail")


def test_openai_live_embedding_provider_maps_url_errors(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(error.URLError("connection refused")),
    )

    try:
        _post_openai_embedding(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "text-embedding-3-large", "input": "hello"},
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT
        assert exc.message == (
            "embeddings.openai request did not complete within the configured timeout."
        )
        assert "connection refused" not in exc.message
    else:
        raise AssertionError("Expected URL failure to map to timeout posture")


def test_openai_live_embedding_provider_posts_successfully_through_urlopen(
    monkeypatch: MonkeyPatch,
) -> None:
    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"model":"text-embedding-3-large","data":[{"embedding":[1,2,3]}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response())

    payload = _post_openai_embedding(
        api_base="https://api.openai.com/v1",
        api_key="secret",
        payload={"model": "text-embedding-3-large", "input": "hello"},
    )

    assert payload["model"] == "text-embedding-3-large"


def test_openai_live_embedding_provider_helpers_cover_fallback_branches() -> None:
    http_error = error.HTTPError(
        url="https://api.openai.com/v1/embeddings",
        code=500,
        msg="Server Error",
        hdrs=Message(),
        fp=BytesIO(b"not json"),
    )

    assert _load_error_payload(http_error) == {}
    assert _as_str(" model ") == " model "
    assert _as_str("   ") is None

    try:
        _extract_embedding({"data": [{"embedding": "invalid"}]})
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    else:
        raise AssertionError("Expected invalid embedding payload to fail")
