from app.config import settings
from app.services.async_worker_execution_service import build_async_worker_execution_catalog


def test_async_worker_execution_catalog_exposes_foundation_default_and_future_options() -> None:
    catalog = build_async_worker_execution_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.active_worker_execution == "in_process_stub"
    assert catalog.worker_count == 3
    assert catalog.workers[0].worker_id == "none"
    assert catalog.workers[0].selection_state == "DOCUMENTED_FOUNDATION_BASELINE"
    assert catalog.workers[0].supports_horizontal_scaling is False
    assert catalog.workers[1].worker_id == "in_process_stub"
    assert catalog.workers[1].enabled is True
    assert catalog.workers[1].selection_state == "ACTIVE_DEFAULT"
    assert catalog.workers[1].supports_job_isolation is True
    assert catalog.workers[2].worker_id == "queue_backed_workers"
    assert catalog.workers[2].execution_class == "DEDICATED_WORKER_FLEET"


def test_async_worker_execution_catalog_reports_queue_backed_workers_as_active() -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    catalog = build_async_worker_execution_catalog()

    assert catalog.active_worker_execution == "queue_backed_workers"
    assert catalog.workers[2].enabled is True
