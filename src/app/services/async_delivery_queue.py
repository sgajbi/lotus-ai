from __future__ import annotations

import importlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Protocol

from app.config import settings


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


class AsyncDeliveryQueue(Protocol):
    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        """Publish one bounded async delivery message."""

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        """Consume one bounded async delivery message when available."""


class NoopAsyncDeliveryQueue:
    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        return AsyncQueueEnqueueResult(
            backend_id="none",
            published=False,
            duplicate_delivery=False,
        )

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        return None


class InMemoryAsyncDeliveryQueue:
    def __init__(self) -> None:
        self._messages_by_id: dict[str, AsyncQueueDeliveryMessage] = {}
        self._delivery_order: list[str] = []

    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        duplicate = message.delivery_id in self._messages_by_id
        if not duplicate:
            self._messages_by_id[message.delivery_id] = deepcopy(message)
            self._delivery_order.append(message.delivery_id)
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
        return None if message is None else deepcopy(message)

    def list_messages(self) -> list[AsyncQueueDeliveryMessage]:
        return [
            deepcopy(self._messages_by_id[key])
            for key in sorted(self._messages_by_id)
        ]


class RedisAsyncDeliveryQueue:
    def __init__(self, *, redis_url: str, queue_name: str) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name

    def enqueue(self, *, message: AsyncQueueDeliveryMessage) -> AsyncQueueEnqueueResult:
        redis_module = importlib.import_module("redis")
        client = redis_module.Redis.from_url(self._redis_url, decode_responses=True)
        dedupe_key = f"{self._queue_name}:dedupe:{message.delivery_id}"
        payload = json.dumps(asdict(message), sort_keys=True)
        if not client.set(dedupe_key, "1", nx=True):
            return AsyncQueueEnqueueResult(
                backend_id="redis_queue",
                published=False,
                duplicate_delivery=True,
            )
        client.rpush(self._queue_name, payload)
        return AsyncQueueEnqueueResult(
            backend_id="redis_queue",
            published=True,
            duplicate_delivery=False,
        )

    def dequeue(self, *, timeout_seconds: int) -> AsyncQueueDeliveryMessage | None:
        redis_module = importlib.import_module("redis")
        client = redis_module.Redis.from_url(self._redis_url, decode_responses=True)
        result = client.blpop(self._queue_name, timeout=timeout_seconds)
        if result is None:
            return None
        _queue_name, payload = result
        loaded = json.loads(payload)
        return AsyncQueueDeliveryMessage(**loaded)


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
