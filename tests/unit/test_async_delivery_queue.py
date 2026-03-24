from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.services.async_delivery_queue import (
    AsyncQueueDeliveryMessage,
    RedisAsyncDeliveryQueue,
    get_test_async_delivery_queue,
)


def test_in_memory_async_delivery_queue_deduplicates_by_delivery_id() -> None:
    queue = get_test_async_delivery_queue()
    message = AsyncQueueDeliveryMessage(
        delivery_id="attempt-001",
        job_id="asyncjob_001",
        attempt_id="attempt-001",
        job_type="retrieval_indexing",
        target_id="retjob_001",
        caller_app="lotus-platform",
        correlation_id="corr-001",
        submitted_at="2026-03-24T00:00:00Z",
    )

    first = queue.enqueue(message=message)
    second = queue.enqueue(message=message)

    assert first.published is True
    assert first.duplicate_delivery is False
    assert second.published is False
    assert second.duplicate_delivery is True
    assert queue.list_messages()[0].job_id == "asyncjob_001"
    assert queue.list_messages()[0].attempt_id == "attempt-001"
    dequeued = queue.dequeue(timeout_seconds=0)
    assert dequeued is not None
    assert dequeued.job_id == "asyncjob_001"
    snapshot = queue.snapshot()
    assert snapshot.pending_delivery_count == 0
    assert snapshot.published_delivery_count == 1
    assert snapshot.dequeued_delivery_count == 1
    assert snapshot.duplicate_delivery_count == 1


def test_in_memory_async_delivery_queue_tracks_redelivery_by_attempt_id() -> None:
    queue = get_test_async_delivery_queue()

    first = queue.enqueue(
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
    second = queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="delivery-002",
            job_id="asyncjob_001",
            attempt_id="attempt-001",
            job_type="retrieval_indexing",
            target_id="retjob_001",
            caller_app="lotus-platform",
            correlation_id="corr-001",
            submitted_at="2026-03-24T00:01:00Z",
        )
    )

    assert first.published is True
    assert second.published is True
    assert queue.snapshot().redelivery_count == 1


def test_redis_async_delivery_queue_pushes_bounded_json_payload(
    monkeypatch: MonkeyPatch,
) -> None:
    published: dict[str, object] = {}

    class FakeRedisClient:
        def __init__(self) -> None:
            self.stats: dict[str, int] = {}

        def set(self, key: str, value: str, nx: bool) -> bool:
            published["dedupe_key"] = key
            published["dedupe_value"] = value
            published["dedupe_nx"] = nx
            return True

        def sadd(self, key: str, value: str) -> int:
            published["attempt_set_key"] = key
            published["attempt_id"] = value
            return 1

        def hincrby(self, key: str, field: str, amount: int) -> None:
            published.setdefault("stats_key", key)
            self.stats[field] = self.stats.get(field, 0) + amount

        def rpush(self, queue_name: str, payload: str) -> None:
            published["queue_name"] = queue_name
            published["payload"] = payload

        def hgetall(self, key: str) -> dict[str, str]:
            return {field: str(value) for field, value in self.stats.items()}

        def llen(self, queue_name: str) -> int:
            return 1

    fake_redis_module = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda url, decode_responses: FakeRedisClient())
    )
    monkeypatch.setattr(
        "app.services.async_delivery_queue.importlib.import_module",
        lambda module_name: fake_redis_module,
    )
    queue = RedisAsyncDeliveryQueue(
        redis_url="redis://localhost:6379/0",
        queue_name="lotus-ai:async:jobs",
    )

    result = queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="attempt-001",
            job_id="asyncjob_001",
            attempt_id="attempt-001",
            job_type="evaluation_execution",
            target_id="provider_runtime_examples",
            caller_app="lotus-platform",
            correlation_id="corr-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )

    assert result.backend_id == "redis_queue"
    assert result.published is True
    assert published["queue_name"] == "lotus-ai:async:jobs"
    assert '"job_id": "asyncjob_001"' in str(published["payload"])
    assert '"attempt_id": "attempt-001"' in str(published["payload"])
