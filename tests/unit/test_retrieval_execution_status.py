from pytest import MonkeyPatch

from app.config import settings
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.retrieval_store import get_retrieval_repository


def test_retrieval_execution_status_reports_disabled_live_execution() -> None:
    status = build_retrieval_execution_status()

    assert status.service == "lotus-ai"
    assert status.retrieval_mode == "disabled"
    assert status.execution_stage == "SEARCH_DISABLED"
    assert status.live_search_enabled is False
    assert status.live_indexing_enabled is True
    assert status.split_route_degraded is False


def test_retrieval_execution_status_reports_enabled_live_execution() -> None:
    settings.retrieval_mode = "enabled"
    get_retrieval_repository().set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    status = build_retrieval_execution_status()

    assert status.retrieval_mode == "enabled"
    assert status.execution_stage == "LIVE_SEARCH"
    assert status.live_search_enabled is True
    assert status.live_indexing_enabled is True
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
    assert "no promoted indexed documents are currently searchable" in status.message.lower()

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
