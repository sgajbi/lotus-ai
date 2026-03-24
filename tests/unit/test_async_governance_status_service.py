from app.config import settings
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


def test_async_governance_status_reports_dedicated_worker_cutover_truth() -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    status = build_async_governance_status()

    assert status.activation_readiness.cutover_state == "dedicated_workers_active"
    assert "dedicated workers are now the active primary path" in status.governance_summary[0]
