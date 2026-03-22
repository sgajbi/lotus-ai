from app.config import settings
from app.services.retrieval_execution_status import build_retrieval_execution_status


def test_retrieval_execution_status_reports_disabled_live_execution() -> None:
    status = build_retrieval_execution_status()

    assert status.service == "lotus-ai"
    assert status.retrieval_mode == "disabled"
    assert status.execution_stage == "SEARCH_DISABLED"
    assert status.live_search_enabled is False
    assert status.live_indexing_enabled is False


def test_retrieval_execution_status_reports_enabled_without_live_backend() -> None:
    settings.retrieval_mode = "enabled"

    status = build_retrieval_execution_status()

    assert status.retrieval_mode == "enabled"
    assert status.execution_stage == "INDEXING_DISABLED"
    assert status.live_search_enabled is False
    assert "no live retrieval execution backend" in status.message

    settings.retrieval_mode = "disabled"
