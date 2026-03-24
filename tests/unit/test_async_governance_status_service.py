from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_test_async_delivery_queue
from app.services.async_governance_status_service import build_async_governance_status


def test_async_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_async_governance_status()

    assert status.service == "lotus-ai"
    assert status.governance_ready is False
    assert status.blocking_area_count == 2
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is False
    assert len(status.governance_summary) == 2
    assert "evaluation execution are active" in status.governance_summary[0]


def test_async_governance_status_reports_dedicated_worker_cutover_truth(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr("app.services.async_operational_state.get_async_delivery_queue", lambda: queue)

    status = build_async_governance_status()

    assert status.activation_readiness.cutover_state == "dedicated_workers_active"
    assert "dedicated workers are now the active primary path" in status.governance_summary[0]


def test_async_governance_status_reports_worker_unavailable_degraded_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    queue.enqueue(
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
    monkeypatch.setattr("app.services.async_operational_state.get_async_delivery_queue", lambda: queue)

    status = build_async_governance_status()

    assert any("queue backlog exists" in summary.lower() for summary in status.governance_summary)
