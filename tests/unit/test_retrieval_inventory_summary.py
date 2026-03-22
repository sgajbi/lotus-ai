from app.contracts.retrieval import RetrievalIndexStatus
from app.retrieval.inventory_summary import (
    summarize_retrieval_runtime_inventory,
    summarize_retrieval_source_inventory,
)


def test_summarize_retrieval_source_inventory_reports_source_counts() -> None:
    summary = summarize_retrieval_source_inventory("lotus-platform-rfcs")

    assert summary.source_id == "lotus-platform-rfcs"
    assert summary.document_count >= 1
    assert summary.chunk_count >= 1
    assert summary.index_status in {
        RetrievalIndexStatus.STAGED,
        RetrievalIndexStatus.INDEXED,
    }


def test_summarize_retrieval_runtime_inventory_reports_seeded_counts() -> None:
    summary = summarize_retrieval_runtime_inventory()

    assert summary.source_count >= 4
    assert summary.document_count >= 4
    assert summary.chunk_count >= 4
    assert summary.index_job_count >= 4
