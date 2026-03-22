from fastapi import HTTPException

from app.services.async_submission_service import submit_async_job
from app.contracts.async_runtime import AsyncJobSubmissionRequest


def test_submit_async_job_returns_rejected_response_for_supported_job_type() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            caller_app="lotus-platform",
            correlation_id="corr-async-001",
            payload_summary="Index newly approved RFC documents.",
        )
    )

    assert response.service == "lotus-ai"
    assert response.submission_status == "REJECTED"
    assert response.accepted is False
    assert response.job_id is None
    assert response.queue_mode == "DISABLED"


def test_submit_async_job_raises_not_found_for_unknown_job_type() -> None:
    try:
        submit_async_job(
            AsyncJobSubmissionRequest(
                job_type="missing_job_type",
                caller_app="lotus-platform",
                correlation_id="corr-async-002",
                payload_summary="Unknown work.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Unknown lotus-ai async job type: missing_job_type"
    else:
        raise AssertionError("Expected async submission to raise HTTPException.")
