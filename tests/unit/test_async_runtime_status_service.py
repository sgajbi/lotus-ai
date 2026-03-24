from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_test_async_delivery_queue
from app.services.async_runtime_status import build_async_runtime_status


def test_async_runtime_status_reports_durable_submission_posture() -> None:
    status = build_async_runtime_status()

    assert status.service == "lotus-ai"
    assert status.cutover_state == "in_process_only"
    assert status.queue_mode == "DISABLED"
    assert status.worker_mode == "IN_PROCESS_ONLY"
    assert status.queue_backend == "none"
    assert status.supported_queue_backends[1].backend_id == "redis_queue"
    assert status.active_worker_execution == "in_process_stub"
    assert status.active_worker_count == 0
    assert status.active_worker_ids == []
    assert status.supported_job_types[0].job_type == "retrieval_indexing"
    assert status.supported_job_types[0].enabled is True
    assert status.supported_job_types[0].execution_path == "durable_runtime_worker_execution"
    assert status.enqueued_job_count == 0
    assert status.recorded_job_count == 2
    assert status.queue_backlog_count == 0
    assert status.duplicate_delivery_count == 0
    assert status.redelivery_count == 0
    assert status.drain_mode_active is False
    assert status.degraded_findings == []
    assert "current cutover state exposes" in status.message


def test_async_runtime_status_reports_dedicated_worker_cutover_truth(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr("app.services.async_operational_state.get_async_delivery_queue", lambda: queue)

    status = build_async_runtime_status()

    assert status.cutover_state == "dedicated_workers_active"
    assert status.queue_mode == "ACTIVE"
    assert status.worker_mode == "DEDICATED"
    assert status.queue_backend == "redis_queue"
    assert status.active_worker_execution == "queue_backed_workers"
    assert status.queue_backlog_count == 0
    assert status.degraded_findings == []


def test_async_runtime_status_reports_backlog_without_active_workers_as_degraded(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="delivery-001",
            job_id="asyncjob_001",
            attempt_id="attempt-001",
            job_type="retrieval_indexing",
            target_id="retjob_001",
            caller_app="lotus-platform",
            correlation_id="corr-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )
    monkeypatch.setattr("app.services.async_operational_state.get_async_delivery_queue", lambda: queue)

    status = build_async_runtime_status()

    assert status.queue_backlog_count == 1
    assert any("no active worker leases" in finding for finding in status.degraded_findings)
