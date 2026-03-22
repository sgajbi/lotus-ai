from app.services.retrieval_catalog_service import (
    get_chunks_for_document,
    get_retrieval_indexing_policy,
    get_retrieval_job_detail_or_raise,
    get_retrieval_job_catalog,
)


def test_get_retrieval_job_catalog_returns_known_jobs() -> None:
    response = get_retrieval_job_catalog()

    assert response.service == "lotus-ai"
    assert any(
        job.source_id == "lotus-platform-rfcs" and job.embedding_record_count >= 2
        for job in response.jobs
    )


def test_get_chunks_for_document_returns_staged_chunks() -> None:
    response = get_chunks_for_document("lotus-platform-rfc-0069")

    assert response.document_id == "lotus-platform-rfc-0069"
    assert response.source_id == "lotus-platform-rfcs"
    assert any(
        chunk.chunk_id == "chunk_rfc_0069_0001"
        and chunk.content_checksum == "sha256:chunk-rfc-0069-0001"
        for chunk in response.chunks
    )


def test_get_retrieval_job_detail_returns_staged_steps() -> None:
    response = get_retrieval_job_detail_or_raise("retjob_lotus_platform_rfcs")

    assert response.job.source_id == "lotus-platform-rfcs"
    assert response.chunking_strategy == "markdown-section-v1"
    assert response.embedding_strategy == "provider-disabled"
    assert response.replay_supported is True
    assert any(step.step_id.endswith(".embedding_generation") for step in response.steps)
    assert any(event.status == "COMPLETED" for event in response.events)


def test_get_retrieval_job_detail_exposes_failed_events_for_blocked_jobs() -> None:
    response = get_retrieval_job_detail_or_raise("retjob_lotus_platform_standards")

    assert any(event.status == "FAILED" for event in response.events)
    assert any("searchable scope" in event.notes for event in response.events)


def test_get_retrieval_indexing_policy_returns_pgvector_strategy() -> None:
    response = get_retrieval_indexing_policy()

    assert response.vector_store == "postgresql+pgvector"
    assert response.persistence_strategy == "postgresql+pgvector"
