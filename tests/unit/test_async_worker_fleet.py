from app.config import settings
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_test_async_delivery_queue
from app.services.async_job_service import build_async_job_detail
from app.services.async_worker_fleet import process_next_async_delivery
from app.services.eval_run_service import build_evaluation_run_detail
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.retrieval_async_execution import submit_retrieval_index_job_async
from app.contracts.evals import EvaluationRunSubmissionRequest


def test_process_next_async_delivery_executes_retrieval_job_in_dedicated_mode(
    monkeypatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-retrieval-001",
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert result is not None
    assert result.job_id == submission.job_id
    assert result.job_type == "retrieval_indexing"
    assert result.handled is True
    assert result.terminal_status == "COMPLETED"
    assert detail.job.status.value == "COMPLETED"


def test_process_next_async_delivery_executes_evaluation_job_in_dedicated_mode(
    monkeypatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-worker-fleet-eval-001",
            triggered_by="operator-a",
        )
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    run_detail = build_evaluation_run_detail(run_id=submission.run_id or "")

    assert result is not None
    assert result.job_id == submission.async_job_id
    assert result.job_type == "evaluation_execution"
    assert result.handled is True
    assert run_detail.run.status.value == "COMPLETED"


def test_process_next_async_delivery_ignores_duplicate_delivery_after_completion(
    monkeypatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-retrieval-duplicate-001",
    )
    first = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="duplicate-delivery-001",
            job_id=submission.job_id or "",
            attempt_id=f"{submission.job_id}_attempt_001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-worker-fleet-retrieval-duplicate-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )

    duplicate = process_next_async_delivery(worker_id="worker-b", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert first is not None
    assert duplicate is None or duplicate.handled is False
    assert detail.job.status.value == "COMPLETED"
