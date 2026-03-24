from pytest import MonkeyPatch

from app.config import settings
from app.contracts.retrieval import RetrievalDocumentGovernanceResponse
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.retrieval_store import get_retrieval_repository


def test_retrieval_execution_status_reports_disabled_live_execution() -> None:
    status = build_retrieval_execution_status()

    assert status.service == "lotus-ai"
    assert status.retrieval_mode == "disabled"
    assert status.execution_stage == "SEARCH_DISABLED"
    assert status.live_search_enabled is False
    assert status.live_indexing_enabled is True
    assert status.embedding_execution_enabled is False
    assert status.refresh_pending_document_count == 0
    assert status.withdrawn_document_count == 0
    assert status.split_route_degraded is False


def test_retrieval_execution_status_reports_enabled_live_execution() -> None:
    settings.retrieval_mode = "enabled"
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"
    get_retrieval_repository().set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    status = build_retrieval_execution_status()

    assert status.retrieval_mode == "enabled"
    assert status.execution_stage == "LIVE_SEARCH"
    assert status.live_search_enabled is True
    assert status.live_indexing_enabled is True
    assert status.embedding_execution_enabled is True
    assert status.embedding_provider_id == "embeddings.openai"
    assert status.refresh_pending_document_count == 0
    assert status.split_route_degraded is False
    assert "searchable promoted document" in status.message

    settings.retrieval_mode = "disabled"


def test_retrieval_execution_status_reports_no_searchable_corpus_after_rollback() -> None:
    settings.retrieval_mode = "enabled"
    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="STAGED",
    )

    status = build_retrieval_execution_status()

    assert status.retrieval_mode == "enabled"
    assert status.execution_stage == "LIVE_SEARCH"
    assert status.live_search_enabled is True
    assert status.split_route_degraded is False
    assert "latest governed corpus lineage is withdrawn" in status.message.lower()

    settings.retrieval_mode = "disabled"


def test_retrieval_execution_status_reports_unready_store_when_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.retrieval_mode = "enabled"

    monkeypatch.setattr(
        "app.services.retrieval_execution_status.get_retrieval_store_runtime_status",
        lambda: type(
            "StoreStatus",
            (),
            {
                "status": "MIGRATION_REQUIRED",
                "detail": "Configured database is reachable but missing required tables: retrieval_sources.",
            },
        )(),
    )

    status = build_retrieval_execution_status()

    assert status.retrieval_mode == "enabled"
    assert status.execution_stage == "INDEXING_DISABLED"
    assert status.live_search_enabled is False
    assert status.split_route_degraded is False
    assert "retrieval store is not ready" in status.message.lower()

    settings.retrieval_mode = "disabled"


def test_retrieval_execution_status_reports_blocked_corpus_after_rollback(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.retrieval_mode = "enabled"
    monkeypatch.setattr(
        "app.services.retrieval_execution_status.build_retrieval_document_governance",
        lambda: RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=1,
            refresh_pending_document_count=0,
            withdrawn_document_count=0,
            documents=[],
        ),
    )

    status = build_retrieval_execution_status()

    assert status.execution_stage == "LIVE_SEARCH"
    assert "rolled back or remains blocked by source posture" in status.message


def test_retrieval_execution_status_reports_empty_registered_corpus(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.retrieval_mode = "enabled"
    monkeypatch.setattr(
        "app.services.retrieval_execution_status.build_retrieval_document_governance",
        lambda: RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=0,
            refresh_pending_document_count=0,
            withdrawn_document_count=0,
            documents=[],
        ),
    )

    status = build_retrieval_execution_status()

    assert status.execution_stage == "LIVE_SEARCH"
    assert "no searchable corpus content is currently registered" in status.message


def test_retrieval_execution_status_reports_refresh_pending_corpus(monkeypatch: MonkeyPatch) -> None:
    settings.retrieval_mode = "enabled"
    monkeypatch.setattr(
        "app.services.retrieval_execution_status.build_retrieval_document_governance",
        lambda: RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=0,
            refresh_pending_document_count=2,
            withdrawn_document_count=0,
            documents=[],
        ),
    )

    status = build_retrieval_execution_status()

    assert status.execution_stage == "LIVE_SEARCH"
    assert status.refresh_pending_document_count == 2
    assert "refresh work is still in flight" in status.message


def test_retrieval_execution_status_reports_withdrawn_corpus(monkeypatch: MonkeyPatch) -> None:
    settings.retrieval_mode = "enabled"
    monkeypatch.setattr(
        "app.services.retrieval_execution_status.build_retrieval_document_governance",
        lambda: RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=0,
            refresh_pending_document_count=0,
            withdrawn_document_count=1,
            documents=[],
        ),
    )

    status = build_retrieval_execution_status()

    assert status.execution_stage == "LIVE_SEARCH"
    assert status.withdrawn_document_count == 1
    assert "latest governed corpus lineage is withdrawn" in status.message
