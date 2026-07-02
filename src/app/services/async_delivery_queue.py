from __future__ import annotations

import importlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any
from typing import Protocol

from app.config import settings


def _is_redis_idle_timeout(exc: Exception) -> bool:
    return (
        exc.__class__.__name__ == "TimeoutError"
        and exc.__class__.__module__.startswith("redis")
    )


@dataclass(frozen=True)
class AsyncQueueDeliveryMessage:
    delivery_id: str
    job_id: str
    attempt_id: str
    job_type: str
    target_id: str | None
    caller_app: str
    correlation_id: str
    submitted_at: str


@dataclass(frozen=True)
class AsyncQueueEnqueueResult:
    backend_id: str
    published: bool
    duplicate_delivery: bool


@dataclass(frozen=True)
class AsyncQueueObservabilitySnapshot:
    backend_id: str
    backend_available: bool
    pending_delivery_count: int
    published_delivery_count: int
    dequeued_delivery_count: int
    duplicate_delivery_count: int
    redelivery_count: int


class AsyncDeliveryQueue(Protocol):
    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        """Publish one bounded async delivery message."""

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        """Consume one bounded async delivery message when available."""

    def snapshot(self) -> AsyncQueueObservabilitySnapshot:
        """Return bounded observability data for the current queue backend."""


class NoopAsyncDeliveryQueue:
    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        return AsyncQueueEnqueueResult(
            backend_id="none",
            published=False,
            duplicate_delivery=False,
        )

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        return None

    def snapshot(self) -> AsyncQueueObservabilitySnapshot:
        return AsyncQueueObservabilitySnapshot(
            backend_id="none",
            backend_available=True,
            pending_delivery_count=0,
            published_delivery_count=0,
            dequeued_delivery_count=0,
            duplicate_delivery_count=0,
            redelivery_count=0,
        )


class InMemoryAsyncDeliveryQueue:
    def __init__(self) -> None:
        self._messages_by_id: dict[str, AsyncQueueDeliveryMessage] = {}
        self._delivery_order: list[str] = []
        self._seen_attempt_ids: set[str] = set()
        self._published_delivery_count = 0
        self._dequeued_delivery_count = 0
        self._duplicate_delivery_count = 0
        self._redelivery_count = 0

    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        duplicate = message.delivery_id in self._messages_by_id
        if duplicate:
            self._duplicate_delivery_count += 1
        else:
            if message.attempt_id in self._seen_attempt_ids:
                self._redelivery_count += 1
            else:
                self._seen_attempt_ids.add(message.attempt_id)
            self._messages_by_id[message.delivery_id] = deepcopy(message)
            self._delivery_order.append(message.delivery_id)
            self._published_delivery_count += 1
        return AsyncQueueEnqueueResult(
            backend_id="redis_queue",
            published=not duplicate,
            duplicate_delivery=duplicate,
        )

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        if not self._delivery_order:
            return None
        delivery_id = self._delivery_order.pop(0)
        message = self._messages_by_id.pop(delivery_id, None)
        if message is not None:
            self._dequeued_delivery_count += 1
        return None if message is None else deepcopy(message)

    def snapshot(self) -> AsyncQueueObservabilitySnapshot:
        return AsyncQueueObservabilitySnapshot(
            backend_id="redis_queue",
            backend_available=True,
            pending_delivery_count=len(self._delivery_order),
            published_delivery_count=self._published_delivery_count,
            dequeued_delivery_count=self._dequeued_delivery_count,
            duplicate_delivery_count=self._duplicate_delivery_count,
            redelivery_count=self._redelivery_count,
        )

    def list_messages(self) -> list[AsyncQueueDeliveryMessage]:
        return [deepcopy(self._messages_by_id[key]) for key in sorted(self._messages_by_id)]


class RedisAsyncDeliveryQueue:
    def __init__(self, *, redis_url: str, queue_name: str) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name

    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        client = self._get_client()
        dedupe_key = f"{self._queue_name}:dedupe:{message.delivery_id}"
        stats_key = f"{self._queue_name}:stats"
        attempt_set_key = f"{self._queue_name}:attempts_seen"
        payload = json.dumps(asdict(message), sort_keys=True)
        if not client.set(dedupe_key, "1", nx=True):
            client.hincrby(stats_key, "duplicate_delivery_count", 1)
            return AsyncQueueEnqueueResult(
                backend_id="redis_queue",
                published=False,
                duplicate_delivery=True,
            )
        if client.sadd(attempt_set_key, message.attempt_id) == 0:
            client.hincrby(stats_key, "redelivery_count", 1)
        client.rpush(self._queue_name, payload)
        client.hincrby(stats_key, "published_delivery_count", 1)
        return AsyncQueueEnqueueResult(
            backend_id="redis_queue",
            published=True,
            duplicate_delivery=False,
        )

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        client = self._get_client()
        try:
            result = client.blpop(self._queue_name, timeout=timeout_seconds)
        except Exception as exc:
            if _is_redis_idle_timeout(exc):
                return None
            raise
        if result is None:
            return None
        client.hincrby(f"{self._queue_name}:stats", "dequeued_delivery_count", 1)
        _queue_name, payload = result
        loaded = json.loads(payload)
        return AsyncQueueDeliveryMessage(**loaded)

    def snapshot(self) -> AsyncQueueObservabilitySnapshot:
        try:
            client = self._get_client()
            stats = client.hgetall(f"{self._queue_name}:stats")
            return AsyncQueueObservabilitySnapshot(
                backend_id="redis_queue",
                backend_available=True,
                pending_delivery_count=int(client.llen(self._queue_name)),
                published_delivery_count=int(stats.get("published_delivery_count", 0)),
                dequeued_delivery_count=int(stats.get("dequeued_delivery_count", 0)),
                duplicate_delivery_count=int(stats.get("duplicate_delivery_count", 0)),
                redelivery_count=int(stats.get("redelivery_count", 0)),
            )
        except Exception:
            return AsyncQueueObservabilitySnapshot(
                backend_id="redis_queue",
                backend_available=False,
                pending_delivery_count=0,
                published_delivery_count=0,
                dequeued_delivery_count=0,
                duplicate_delivery_count=0,
                redelivery_count=0,
            )

    def _get_client(self) -> Any:
        redis_module = importlib.import_module("redis")
        return redis_module.Redis.from_url(self._redis_url, decode_responses=True)


_memory_queue: InMemoryAsyncDeliveryQueue | None = None
_redis_queue: RedisAsyncDeliveryQueue | None = None


def get_async_delivery_queue() -> AsyncDeliveryQueue:
    if settings.async_queue_backend_mode == "none":
        return NoopAsyncDeliveryQueue()
    if settings.async_queue_backend_mode == "redis":
        if not settings.async_queue_redis_url:
            raise RuntimeError(
                "LOTUS_AI_ASYNC_QUEUE_REDIS_URL is required when LOTUS_AI_ASYNC_QUEUE_BACKEND_MODE=redis."
            )
        global _redis_queue
        if _redis_queue is None:
            _redis_queue = RedisAsyncDeliveryQueue(
                redis_url=settings.async_queue_redis_url,
                queue_name=settings.async_queue_name,
            )
        return _redis_queue
    raise RuntimeError("Unsupported LOTUS_AI_ASYNC_QUEUE_BACKEND_MODE.")


def get_test_async_delivery_queue() -> InMemoryAsyncDeliveryQueue:
    global _memory_queue
    if _memory_queue is None:
        _memory_queue = InMemoryAsyncDeliveryQueue()
    return _memory_queue


def reset_async_delivery_queue_cache() -> None:
    global _memory_queue
    global _redis_queue
    _memory_queue = None
    _redis_queue = None
