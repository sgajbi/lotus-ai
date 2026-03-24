from app.config import settings
from app.services.retrieval_embedding_runtime import build_retrieval_embedding_runtime


def test_retrieval_embedding_runtime_defaults_to_disabled_fallback() -> None:
    runtime = build_retrieval_embedding_runtime()

    assert runtime.embedding_execution_enabled is False
    assert runtime.embedding_strategy == "provider-disabled"
    assert any(
        "stub embedding path" in finding or "not enabled" in finding for finding in runtime.findings
    )


def test_retrieval_embedding_runtime_reports_stub_strategy() -> None:
    settings.embedding_provider_mode = "stub"

    runtime = build_retrieval_embedding_runtime()

    assert runtime.embedding_execution_enabled is False
    assert runtime.embedding_strategy == "provider-stub"
    assert any("stub embedding path" in finding for finding in runtime.findings)


def test_retrieval_embedding_runtime_reports_live_strategy() -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    runtime = build_retrieval_embedding_runtime()

    assert runtime.embedding_execution_enabled is True
    assert runtime.embedding_provider_id == "embeddings.openai"
    assert runtime.embedding_model_id == "text-embedding-3-large"
    assert runtime.embedding_strategy == "provider-live-openai"
