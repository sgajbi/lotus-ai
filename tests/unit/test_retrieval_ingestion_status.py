from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.retrieval_ingestion_status import build_retrieval_ingestion_status


def test_retrieval_ingestion_status_reports_durable_lineage_state() -> None:
    settings.retrieval_store_mode = "memory"

    status = build_retrieval_ingestion_status()

    assert status.ingestion_delivery_stage == "OPERATIONALLY_HARDENED"
    assert status.live_ingestion_enabled is True
    assert status.document_version_count >= 5
    assert status.superseded_document_version_count >= 1
    assert status.withdrawn_document_version_count >= 1
    assert status.blocked_ingestion_job_count >= 1
    assert status.running_ingestion_job_count == 0
    assert status.failed_ingestion_job_count == 0
    assert status.completed_ingestion_job_count == 0
    assert status.artifact_backed_job_count == 0
    assert status.recent_document_versions
    assert status.recent_ingestion_jobs


def test_retrieval_ingestion_status_reports_catalog_only_when_store_is_unavailable(
    monkeypatch: MonkeyPatch,
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


def test_retrieval_ingestion_status_reports_artifact_backed_runtime_diagnostics() -> None:
    from app.services.retrieval_ingestion_async_execution import (
        run_next_retrieval_ingestion_job,
        submit_retrieval_ingestion_job_async,
    )

    submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ret-ingestion-status-artifacts",
    )
    run_next_retrieval_ingestion_job(worker_id="worker-a")

    status = build_retrieval_ingestion_status()

    assert status.completed_ingestion_job_count >= 1
    assert status.artifact_backed_job_count >= 1
    assert any(job.artifact_refs for job in status.recent_ingestion_jobs)


def test_retrieval_ingestion_status_degrades_when_artifact_review_path_is_not_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_status.build_artifact_runtime_status",
        lambda: type(
            "ArtifactRuntime",
            (),
            {
                "metadata_store": type(
                    "MetadataStore",
                    (),
                    {"status": RuntimeReadinessStatus.READY},
                )(),
                "object_store": type(
                    "ObjectStore",
                    (),
                    {"status": RuntimeReadinessStatus.CONFIGURATION_REQUIRED},
                )(),
            },
        )(),
    )

    status = build_retrieval_ingestion_status()

    assert status.ingestion_delivery_stage == "RUNTIME_CONVERGED"
    assert any(
        "artifact-backed corpus-change diagnostics" in finding
        for finding in status.runtime_findings
    )


def test_retrieval_ingestion_status_reports_durable_state_when_async_execution_is_disabled(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_status.get_async_job_type_descriptor",
        lambda job_type: None,
    )

    status = build_retrieval_ingestion_status()

    assert status.ingestion_delivery_stage == "DURABLE_STATE_READY"
    assert any(
        "Live ingestion execution remains disabled" in finding
        for finding in status.runtime_findings
    )


def test_retrieval_ingestion_status_reports_failed_terminal_jobs() -> None:
    from app.services.async_submission_service import submit_async_job
    from app.contracts.async_runtime import AsyncJobSubmissionRequest
    from app.services.retrieval_ingestion_async_execution import (
        run_next_retrieval_ingestion_job,
    )

    submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="document_ingestion",
            target_id="ingjob_lotus_openapi_onboard_pending",
            caller_app="lotus-platform",
            correlation_id="corr-ret-ingestion-status-failed-001",
            payload_summary="failed ingestion status review",
        )
    )
    run_next_retrieval_ingestion_job(worker_id="worker-a")

    status = build_retrieval_ingestion_status()

    assert status.failed_ingestion_job_count >= 1
    assert any("failed terminal posture" in finding for finding in status.runtime_findings)
