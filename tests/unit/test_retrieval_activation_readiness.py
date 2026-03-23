from app.config import settings
from app.services.retrieval_store import get_retrieval_repository
from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness


def test_retrieval_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_retrieval_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.retrieval_mode == "disabled"
    assert readiness.embedding_provider_mode == "disabled"
    assert readiness.activation_ready is False
    assert any("Retrieval mode is not enabled" in finding for finding in readiness.blocking_findings)
    assert any(
        "runtime-backed live-search evidence exists" in finding
        for finding in readiness.blocking_findings
    )
    assert len(readiness.activation_path) == 4


def test_retrieval_activation_readiness_reports_live_mode_with_remaining_governance_gaps() -> None:
    settings.retrieval_mode = "enabled"
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
    assert any(
        "Embedding provider execution is still disabled" in finding
        for finding in readiness.blocking_findings
    )
