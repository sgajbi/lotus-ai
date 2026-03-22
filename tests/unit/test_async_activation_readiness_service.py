from app.services.async_activation_readiness_service import build_async_activation_readiness


def test_async_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_async_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.activation_ready is False
    assert readiness.queue_backend == "none"
    assert readiness.worker_execution == "none"
    assert readiness.supported_job_type_count == 3
    assert len(readiness.blocking_findings) == 4
    assert "foundation phase" in readiness.blocking_findings[0]
    assert len(readiness.activation_path) == 4
