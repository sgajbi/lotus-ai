import pytest

from app.config import settings
from app.services.async_runtime_posture import get_async_runtime_posture


def test_async_runtime_posture_defaults_to_in_process_only() -> None:
    posture = get_async_runtime_posture()

    assert posture.cutover_state == "in_process_only"
    assert posture.queue_mode == "DISABLED"
    assert posture.worker_mode == "IN_PROCESS_ONLY"
    assert posture.queue_backend == "none"
    assert posture.active_worker_execution == "in_process_stub"


def test_async_runtime_posture_requires_redis_for_queue_shadow() -> None:
    settings.async_cutover_state = "queue_delivery_shadow"

    with pytest.raises(RuntimeError, match="ASYNC_QUEUE_BACKEND_MODE=redis"):
        get_async_runtime_posture()
