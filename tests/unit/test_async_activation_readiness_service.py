from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_test_async_delivery_queue
from app.services.async_activation_readiness_service import build_async_activation_readiness


def test_async_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_async_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.activation_ready is False
    assert readiness.cutover_state == "in_process_only"
    assert readiness.queue_backend == "none"
    assert readiness.worker_execution == "in_process_stub"
    assert readiness.supported_job_type_count == 3
    assert len(readiness.blocking_findings) == 2
    assert "queue-backed worker execution is not the active primary path yet" in readiness.blocking_findings[0]
    assert "evaluation execution are active" in readiness.blocking_findings[1]
    assert len(readiness.activation_path) == 2


def test_async_activation_readiness_reports_shadow_cutover_truth() -> None:
    settings.async_cutover_state = "queue_delivery_shadow"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    readiness = build_async_activation_readiness()

    assert readiness.cutover_state == "queue_delivery_shadow"
    assert readiness.queue_backend == "redis_queue"
    assert readiness.worker_execution == "in_process_stub"
    assert "shadow mode" in readiness.blocking_findings[0]


def test_async_activation_readiness_reports_dedicated_worker_cutover_truth(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr("app.services.async_operational_state.get_async_delivery_queue", lambda: queue)

    readiness = build_async_activation_readiness()

    assert readiness.cutover_state == "dedicated_workers_active"
    assert readiness.queue_backend == "redis_queue"
    assert readiness.worker_execution == "queue_backed_workers"
    assert len(readiness.blocking_findings) == 1


def test_async_activation_readiness_reports_drain_mode_as_blocking(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    settings.async_worker_drain_enabled = True
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

    readiness = build_async_activation_readiness()

    assert any("drain mode" in finding for finding in readiness.blocking_findings)


def test_async_activation_readiness_reports_degraded_fallback_truth() -> None:
    settings.async_cutover_state = "degraded_fallback"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    readiness = build_async_activation_readiness()

    assert readiness.cutover_state == "degraded_fallback"
    assert readiness.worker_mode == "DEGRADED_FALLBACK"
    assert any("degraded fallback" in finding for finding in readiness.blocking_findings)
