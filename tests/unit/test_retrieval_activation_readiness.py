from pytest import MonkeyPatch

from app.config import settings
from app.contracts.retrieval import RetrievalDocumentGovernanceResponse
from app.services.retrieval_store import get_retrieval_repository
from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness


def test_retrieval_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_retrieval_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.retrieval_mode == "disabled"
    assert readiness.embedding_provider_mode == "disabled"
    assert readiness.embedding_execution_enabled is False
    assert readiness.activation_ready is False
    assert any(
        "Retrieval mode is not enabled" in finding for finding in readiness.blocking_findings
    )
    assert any(
        "runtime-backed live-search evidence exists" in finding
        for finding in readiness.blocking_findings
    )
    assert len(readiness.activation_path) == 4


def test_retrieval_activation_readiness_reports_live_mode_with_remaining_governance_gaps() -> None:
    settings.retrieval_mode = "enabled"
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"
    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    readiness = build_retrieval_activation_readiness()

    assert readiness.activation_ready is False
    assert not any(
        "No promoted indexed documents are currently searchable" in finding
        for finding in readiness.blocking_findings
    )
    assert any(
        "runbook readiness remains incomplete" in finding for finding in readiness.blocking_findings
    )
    assert readiness.embedding_execution_enabled is True


def test_retrieval_activation_readiness_reports_unready_store_blocking(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.retrieval_mode = "enabled"

    monkeypatch.setattr(
        "app.services.retrieval_activation_readiness.get_retrieval_store_runtime_status",
        lambda: type(
            "StoreStatus",
            (),
            {
                "status": "MIGRATION_REQUIRED",
                "detail": "Configured database is reachable but missing required tables: retrieval_sources.",
            },
        )(),
    )

    readiness = build_retrieval_activation_readiness()

    assert readiness.activation_ready is False
    assert any(
        "Retrieval store readiness is blocking live search activation" in finding
        for finding in readiness.blocking_findings
    )


def test_retrieval_activation_readiness_reports_blocked_corpus_path(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.retrieval_mode = "enabled"
    monkeypatch.setattr(
        "app.services.retrieval_activation_readiness.build_retrieval_document_governance",
        lambda: RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=2,
            documents=[],
        ),
    )

    readiness = build_retrieval_activation_readiness()

    assert readiness.activation_ready is False
    assert any(
        "governed corpus is blocked or rolled back" in finding
        for finding in readiness.blocking_findings
    )


def test_retrieval_activation_readiness_reports_no_registered_live_corpus(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.retrieval_mode = "enabled"
    monkeypatch.setattr(
        "app.services.retrieval_activation_readiness.build_retrieval_document_governance",
        lambda: RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=0,
            documents=[],
        ),
    )

    readiness = build_retrieval_activation_readiness()

    assert readiness.activation_ready is False
    assert any(
        "currently registered for the live retrieval path" in finding
        for finding in readiness.blocking_findings
    )
