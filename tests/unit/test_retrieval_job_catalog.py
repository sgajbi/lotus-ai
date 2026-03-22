from app.services.retrieval_catalog_service import (
    get_chunks_for_document,
    get_retrieval_indexing_policy,
    get_retrieval_job_detail_or_raise,
    get_retrieval_job_catalog,
)


def test_get_retrieval_job_catalog_returns_known_jobs() -> None:
    response = get_retrieval_job_catalog()

    assert response.service == "lotus-ai"
    assert any(job.source_id == "lotus-platform-rfcs" for job in response.jobs)


def test_get_chunks_for_document_returns_staged_chunks() -> None:
    response = get_chunks_for_document("lotus-platform-rfc-0069")

    assert response.document_id == "lotus-platform-rfc-0069"
    assert response.source_id == "lotus-platform-rfcs"
    assert any(chunk.chunk_id == "chunk_rfc_0069_0001" for chunk in response.chunks)


def test_get_retrieval_job_detail_returns_staged_steps() -> None:
    response = get_retrieval_job_detail_or_raise("retjob_lotus_platform_rfcs")

    assert response.job.source_id == "lotus-platform-rfcs"
    assert any(step.step_id.endswith(".embedding_generation") for step in response.steps)


def test_get_retrieval_indexing_policy_returns_pgvector_strategy() -> None:
    response = get_retrieval_indexing_policy()

    assert response.vector_store == "postgresql+pgvector"
    assert response.persistence_strategy == "postgresql+pgvector"
