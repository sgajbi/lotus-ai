from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository


def test_memory_retrieval_repository_returns_seeded_sources() -> None:
    repository = InMemoryRetrievalRepository()

    sources = repository.list_sources()

    assert any(source.source_id == "lotus-platform-rfcs" for source in sources)


def test_memory_retrieval_repository_returns_seeded_document_and_chunks() -> None:
    repository = InMemoryRetrievalRepository()

    document = repository.get_document("lotus-platform-rfc-0069")
    chunks = repository.list_chunks_for_document("lotus-platform-rfc-0069")

    assert document is not None
    assert document.source_id == "lotus-platform-rfcs"
    assert any(chunk.chunk_id == "chunk_rfc_0069_0001" for chunk in chunks)
