from app.services.async_worker_runtime import claim_next_async_job, complete_async_job, start_async_job
from fastapi.testclient import TestClient


def test_async_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["queue_mode"] == "STUBBED"
    assert body["worker_mode"] == "STUBBED"
    assert body["queue_backend"] == "service_database"
    assert body["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["supported_queue_backends"][1]["backend_id"] == "service_database"
    assert body["active_worker_execution"] == "in_process_stub"
    assert body["supported_worker_executions"][0]["worker_id"] == "none"
    assert body["supported_worker_executions"][2]["worker_id"] == "queue_backed_workers"
    assert body["active_worker_count"] == 0
    assert body["enqueued_job_count"] == 0
    assert body["recorded_job_count"] == 2
    assert body["supported_job_types"][0]["enabled"] is True
    assert any(job["job_type"] == "retrieval_indexing" for job in body["supported_job_types"])


def test_async_queue_backend_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/async/queue-backends")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["active_queue_backend"] == "service_database"
    assert body["backend_count"] == 4
    assert body["backends"][0]["backend_id"] == "none"
    assert body["backends"][1]["backend_id"] == "service_database"
    assert body["backends"][2]["backend_id"] == "redis_queue"
    assert body["backends"][3]["backend_id"] == "kafka_orchestrated"


def test_async_worker_execution_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/async/worker-executions")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["active_worker_execution"] == "in_process_stub"
    assert body["worker_count"] == 3
    assert body["workers"][0]["worker_id"] == "none"
    assert body["workers"][1]["worker_id"] == "in_process_stub"
    assert body["workers"][1]["enabled"] is True
    assert body["workers"][2]["worker_id"] == "queue_backed_workers"


def test_async_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/async/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["activation_ready"] is False
    assert body["queue_backend"] == "service_database"
    assert body["worker_execution"] == "in_process_stub"
    assert body["supported_job_type_count"] == 3
    assert len(body["blocking_findings"]) == 2
    assert len(body["activation_path"]) == 2


def test_async_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/async/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "async_operational_runbook"
    assert body["items"][1]["status"] == "NOT_READY"


def test_async_governance_status_route(client: TestClient) -> None:
    response = client.get("/platform/async/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["governance_ready"] is False
    assert body["blocking_area_count"] == 2
    assert body["activation_readiness"]["activation_ready"] is False
    assert body["runbook_readiness"]["runbook_ready"] is False
    assert len(body["governance_summary"]) == 2


def test_async_job_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/async/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["job_count"] == 2
    assert body["queued_job_count"] == 0
    assert body["jobs"][0]["job_id"] == "asyncjob_retrieval_indexing_001"
    assert body["jobs"][0]["status"] == "STAGED"
    assert body["jobs"][0]["record_source"] == "STAGED_ARTIFACT"
    assert body["jobs"][1]["status"] == "SUPERSEDED"
    assert body["jobs"][1]["related_evaluation_run_id"] == "foundation_eval_2026_03_21_001"


def test_async_job_detail_route(client: TestClient) -> None:
    response = client.get("/platform/async/jobs/asyncjob_retrieval_indexing_001")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["job"]["job_type"] == "retrieval_indexing"
    assert body["job"]["status"] == "STAGED"
    assert body["job"]["record_source"] == "STAGED_ARTIFACT"
    assert body["job"]["related_evaluation_run_id"] is None
    assert body["attempts"] == []
    assert body["active_lease"] is None


def test_async_job_detail_route_returns_not_found_for_unknown_job(client: TestClient) -> None:
    response = client.get("/platform/async/jobs/missing_async_job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Async job artifact 'missing_async_job' was not found."


def test_async_job_submit_route_accepts_runtime_backed_submission(client: TestClient) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-001",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["submission_status"] == "ACCEPTED"
    assert body["accepted"] is True
    assert body["job_id"] is not None
    assert body["queue_mode"] == "STUBBED"
    assert body["worker_mode"] == "STUBBED"

    catalog_response = client.get("/platform/async/jobs")
    catalog_body = catalog_response.json()
    runtime_job = next(job for job in catalog_body["jobs"] if job["job_id"] == body["job_id"])

    assert catalog_body["queued_job_count"] == 1
    assert runtime_job["status"] == "QUEUED"
    assert runtime_job["record_source"] == "RUNTIME_STATE"


def test_async_job_detail_route_exposes_runtime_attempt_and_lease_history(
    client: TestClient,
) -> None:
    submit_response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-claim-001",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )
    job_id = submit_response.json()["job_id"]
    claim_next_async_job(worker_id="worker-a")
    start_async_job(job_id=job_id, worker_id="worker-a")

    running_response = client.get(f"/platform/async/jobs/{job_id}")

    assert running_response.status_code == 200
    running_body = running_response.json()
    assert running_body["job"]["status"] == "RUNNING"
    assert running_body["attempts"][0]["status"] == "RUNNING"
    assert running_body["attempts"][0]["worker_id"] == "worker-a"
    assert running_body["active_lease"]["worker_id"] == "worker-a"

    complete_async_job(
        job_id=job_id,
        worker_id="worker-a",
        message="Retrieval indexing completed successfully.",
    )
    completed_response = client.get(f"/platform/async/jobs/{job_id}")
    completed_body = completed_response.json()

    assert completed_body["job"]["status"] == "COMPLETED"
    assert completed_body["attempts"][0]["status"] == "COMPLETED"
    assert completed_body["active_lease"] is None


def test_async_job_submit_route_rejects_documentation_only_job_type(client: TestClient) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "evaluation_execution",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-001-eval",
            "payload_summary": "Run staged evaluation family.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission_status"] == "REJECTED"
    assert body["accepted"] is False
    assert body["job_id"] is None
    assert body["queue_mode"] == "STUBBED"
    assert body["worker_mode"] == "STUBBED"


def test_async_job_submit_route_returns_not_found_for_unknown_job_type(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "missing_job_type",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-002",
            "payload_summary": "Unknown async work.",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown lotus-ai async job type: missing_job_type"
