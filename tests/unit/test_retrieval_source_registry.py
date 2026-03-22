from app.retrieval.source_registry import VECTOR_STORE_STRATEGY, list_retrieval_sources


def test_list_retrieval_sources_returns_pgvector_strategy() -> None:
    catalog = list_retrieval_sources()

    assert catalog.service == "lotus-ai"
    assert catalog.vector_store == VECTOR_STORE_STRATEGY
    assert len(catalog.sources) >= 4
    assert any(source.source_id == "lotus-platform-rfcs" for source in catalog.sources)
