from app.services.async_job_service import build_async_job_detail
from app.services.retrieval_async_execution import (
    run_next_retrieval_index_job,
    submit_retrieval_index_job_async,
)
from app.services.retrieval_catalog_service import (
    get_documents_for_source,
    get_retrieval_job_detail_or_raise,
)


def test_submit_retrieval_index_job_async_targets_concrete_retrieval_job() -> None:
    response = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-ret-async-001",
    )

    assert response.accepted is True
    assert response.target_id == "retjob_lotus_platform_rfcs"

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.target_id == "retjob_lotus_platform_rfcs"
    assert detail.job.status.value == "QUEUED"


def test_run_next_retrieval_index_job_completes_and_updates_retrieval_state() -> None:
    submit_response = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-ret-async-002",
    )

    result = run_next_retrieval_index_job(worker_id="worker-a")

    assert result is not None
    assert result.async_job_id == submit_response.job_id
    assert result.retrieval_job_id == "retjob_lotus_platform_rfcs"
    assert result.terminal_status == "COMPLETED"

    async_detail = build_async_job_detail(job_id=submit_response.job_id or "")
    retrieval_detail = get_retrieval_job_detail_or_raise("retjob_lotus_platform_rfcs")
    source_documents = get_documents_for_source("lotus-platform-rfcs")

    assert async_detail.job.status.value == "COMPLETED"
    assert retrieval_detail.job.status.value == "COMPLETED"
    assert retrieval_detail.steps[2].runtime_status == "COMPLETED"
    assert retrieval_detail.steps[2].linked_async_job_id == submit_response.job_id
    assert all(document.index_status.value == "INDEXED" for document in source_documents.documents)
