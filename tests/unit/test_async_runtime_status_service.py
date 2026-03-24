from app.services.async_runtime_status import build_async_runtime_status


def test_async_runtime_status_reports_durable_submission_posture() -> None:
    status = build_async_runtime_status()

    assert status.service == "lotus-ai"
    assert status.cutover_state == "in_process_only"
    assert status.queue_mode == "DISABLED"
    assert status.worker_mode == "IN_PROCESS_ONLY"
    assert status.queue_backend == "none"
    assert status.supported_queue_backends[1].backend_id == "redis_queue"
    assert status.active_worker_execution == "in_process_stub"
    assert status.active_worker_count == 0
    assert status.supported_job_types[0].job_type == "retrieval_indexing"
    assert status.supported_job_types[0].enabled is True
    assert status.supported_job_types[0].execution_path == "durable_runtime_worker_execution"
    assert status.enqueued_job_count == 0
    assert status.recorded_job_count == 2
    assert "current cutover state exposes" in status.message
