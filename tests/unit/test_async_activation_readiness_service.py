from app.config import settings
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


def test_async_activation_readiness_reports_dedicated_worker_cutover_truth() -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    readiness = build_async_activation_readiness()

    assert readiness.cutover_state == "dedicated_workers_active"
    assert readiness.queue_backend == "redis_queue"
    assert readiness.worker_execution == "queue_backed_workers"
    assert len(readiness.blocking_findings) == 1
