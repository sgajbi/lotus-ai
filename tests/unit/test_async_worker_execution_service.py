from app.services.async_worker_execution_service import build_async_worker_execution_catalog


def test_async_worker_execution_catalog_exposes_foundation_default_and_future_options() -> None:
    catalog = build_async_worker_execution_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.active_worker_execution == "none"
    assert catalog.worker_count == 3
    assert catalog.workers[0].worker_id == "none"
    assert catalog.workers[0].selection_state == "ACTIVE_FOUNDATION_DEFAULT"
    assert catalog.workers[0].supports_horizontal_scaling is False
    assert catalog.workers[1].worker_id == "in_process_stub"
    assert catalog.workers[1].supports_job_isolation is True
    assert catalog.workers[2].worker_id == "queue_backed_workers"
    assert catalog.workers[2].execution_class == "DEDICATED_WORKER_FLEET"
