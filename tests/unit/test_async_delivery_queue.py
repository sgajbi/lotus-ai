from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch
import pytest

from app.config import settings
from app.services.async_delivery_queue import (
    AsyncQueueDeliveryMessage,
    RedisAsyncDeliveryQueue,
    get_async_delivery_queue,
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


def test_get_async_delivery_queue_returns_noop_backend_when_disabled() -> None:
    settings.async_queue_backend_mode = "none"

    queue = get_async_delivery_queue()
    result = queue.enqueue(
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

    assert result.backend_id == "none"
    assert result.published is False
    assert queue.dequeue(timeout_seconds=0) is None
    assert queue.snapshot().backend_id == "none"


def test_get_async_delivery_queue_rejects_redis_without_url() -> None:
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = None

    with pytest.raises(RuntimeError, match="LOTUS_AI_ASYNC_QUEUE_REDIS_URL"):
        get_async_delivery_queue()


def test_get_async_delivery_queue_rejects_unsupported_backend() -> None:
    settings.async_queue_backend_mode = "unsupported"

    with pytest.raises(RuntimeError, match="Unsupported LOTUS_AI_ASYNC_QUEUE_BACKEND_MODE"):
        get_async_delivery_queue()


def test_redis_async_delivery_queue_dequeues_and_reports_snapshot(
    monkeypatch: MonkeyPatch,
) -> None:
    published: dict[str, object] = {}

    class FakeRedisClient:
        def __init__(self) -> None:
            self.stats: dict[str, int] = {
                "published_delivery_count": 1,
                "dequeued_delivery_count": 0,
                "duplicate_delivery_count": 0,
                "redelivery_count": 0,
            }

        def blpop(self, queue_name: str, timeout: int) -> tuple[str, str]:
            published["queue_name"] = queue_name
            published["timeout"] = timeout
            return (
                queue_name,
                '{"attempt_id":"attempt-001","caller_app":"lotus-platform","correlation_id":"corr-001","delivery_id":"delivery-001","job_id":"asyncjob_001","job_type":"retrieval_indexing","submitted_at":"2026-03-24T00:00:00Z","target_id":"retjob_001"}',
            )

        def hincrby(self, key: str, field: str, amount: int) -> None:
            self.stats[field] = self.stats.get(field, 0) + amount

        def hgetall(self, key: str) -> dict[str, str]:
            return {field: str(value) for field, value in self.stats.items()}

        def llen(self, queue_name: str) -> int:
            return 0

    fake_client = FakeRedisClient()
    fake_redis_module = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda url, decode_responses: fake_client)
    )
    monkeypatch.setattr(
        "app.services.async_delivery_queue.importlib.import_module",
        lambda module_name: fake_redis_module,
    )
    queue = RedisAsyncDeliveryQueue(
        redis_url="redis://localhost:6379/0",
        queue_name="lotus-ai:async:jobs",
    )

    message = queue.dequeue(timeout_seconds=3)
    snapshot = queue.snapshot()

    assert message is not None
    assert message.job_id == "asyncjob_001"
    assert published["timeout"] == 3
    assert snapshot.pending_delivery_count == 0
    assert snapshot.dequeued_delivery_count == 1


def test_redis_async_delivery_queue_treats_idle_timeout_as_empty_queue(
    monkeypatch: MonkeyPatch,
) -> None:
    redis_timeout_error = type(
        "TimeoutError",
        (Exception,),
        {"__module__": "redis.exceptions"},
    )

    class FakeRedisClient:
        def blpop(self, queue_name: str, timeout: int) -> None:
            raise redis_timeout_error("Timeout reading from socket")

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

    assert queue.dequeue(timeout_seconds=3) is None


def test_redis_async_delivery_queue_snapshot_reports_backend_unavailable(
    monkeypatch: MonkeyPatch,
) -> None:
    class FailingRedisClient:
        def hgetall(self, key: str) -> dict[str, str]:
            raise RuntimeError("redis unavailable")

    fake_redis_module = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda url, decode_responses: FailingRedisClient())
    )
    monkeypatch.setattr(
        "app.services.async_delivery_queue.importlib.import_module",
        lambda module_name: fake_redis_module,
    )
    queue = RedisAsyncDeliveryQueue(
        redis_url="redis://localhost:6379/0",
        queue_name="lotus-ai:async:jobs",
    )

    snapshot = queue.snapshot()

    assert snapshot.backend_available is False
    assert snapshot.pending_delivery_count == 0
