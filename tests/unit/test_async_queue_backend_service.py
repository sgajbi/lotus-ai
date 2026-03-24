from app.config import settings
from app.services.async_queue_backend_service import build_async_queue_backend_catalog


def test_async_queue_backend_catalog_exposes_foundation_default_and_future_options() -> None:
    catalog = build_async_queue_backend_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.active_queue_backend == "none"
    assert catalog.backend_count == 3
    assert catalog.backends[0].backend_id == "none"
    assert catalog.backends[0].selection_state == "ACTIVE_DEFAULT"
    assert catalog.backends[0].supports_durable_queue is False
    assert catalog.backends[1].backend_id == "redis_queue"
    assert catalog.backends[1].enabled is False
    assert catalog.backends[1].supports_durable_queue is True
    assert catalog.backends[1].supports_worker_scaling is True
    assert catalog.backends[2].backend_id == "kafka_orchestrated"
    assert catalog.backends[2].backend_class == "EVENT_STREAM_BRIDGE"


def test_async_queue_backend_catalog_reports_redis_as_active_when_dedicated_cutover_enabled() -> (
    None
):
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    catalog = build_async_queue_backend_catalog()

    assert catalog.active_queue_backend == "redis_queue"
    assert catalog.backends[1].enabled is True
