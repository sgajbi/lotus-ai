from app.services.async_queue_backend_service import build_async_queue_backend_catalog


def test_async_queue_backend_catalog_exposes_foundation_default_and_future_options() -> None:
    catalog = build_async_queue_backend_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.active_queue_backend == "service_database"
    assert catalog.backend_count == 4
    assert catalog.backends[0].backend_id == "none"
    assert catalog.backends[0].selection_state == "DOCUMENTED_FOUNDATION_BASELINE"
    assert catalog.backends[0].supports_durable_queue is False
    assert catalog.backends[1].backend_id == "service_database"
    assert catalog.backends[1].enabled is True
    assert catalog.backends[1].supports_durable_queue is True
    assert catalog.backends[2].backend_id == "redis_queue"
    assert catalog.backends[2].supports_worker_scaling is True
    assert catalog.backends[3].backend_id == "kafka_orchestrated"
    assert catalog.backends[3].backend_class == "EVENT_STREAM_BRIDGE"
