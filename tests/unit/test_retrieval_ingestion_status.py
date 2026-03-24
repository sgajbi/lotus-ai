from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.retrieval_ingestion_status import build_retrieval_ingestion_status


def test_retrieval_ingestion_status_reports_durable_lineage_state() -> None:
    settings.retrieval_store_mode = "memory"

    status = build_retrieval_ingestion_status()

    assert status.ingestion_delivery_stage == "ASYNC_EXECUTION_READY"
    assert status.live_ingestion_enabled is True
    assert status.document_version_count >= 5
    assert status.superseded_document_version_count >= 1
    assert status.withdrawn_document_version_count >= 1
    assert status.blocked_ingestion_job_count >= 1
    assert status.recent_document_versions
    assert status.recent_ingestion_jobs


def test_retrieval_ingestion_status_reports_catalog_only_when_store_is_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_status.get_retrieval_store_runtime_status",
        lambda: type(
            "StoreStatus",
            (),
            {
                "status": RuntimeReadinessStatus.UNAVAILABLE,
                "detail": "database missing",
                "database_configured": False,
            },
        )(),
    )

    status = build_retrieval_ingestion_status()

    assert status.ingestion_delivery_stage == "CATALOG_ONLY"
    assert status.document_version_count == 0
    assert status.ingestion_job_count == 0
    assert status.runtime_findings
