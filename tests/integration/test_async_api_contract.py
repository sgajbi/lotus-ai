from fastapi.testclient import TestClient
from app.config import settings


def test_async_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["queue_mode"] == "DISABLED"
    assert body["worker_mode"] == "DOCUMENTED_ONLY"
    assert body["queue_backend"] == "none"
    assert body["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["supported_queue_backends"][1]["backend_id"] == "redis_queue"
    assert body["active_worker_execution"] == "none"
    assert body["supported_worker_executions"][0]["worker_id"] == "none"
    assert body["supported_worker_executions"][2]["worker_id"] == "queue_backed_workers"
    assert body["active_worker_count"] == 0
    assert body["enqueued_job_count"] == 1
    assert body["recorded_job_count"] == 2
    assert any(job["job_type"] == "retrieval_indexing" for job in body["supported_job_types"])


def test_async_queue_backend_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/async/queue-backends")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["active_queue_backend"] == "none"
    assert body["backend_count"] == 3
    assert body["backends"][0]["backend_id"] == "none"
    assert body["backends"][1]["backend_id"] == "redis_queue"
    assert body["backends"][2]["backend_id"] == "kafka_orchestrated"


def test_async_worker_execution_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/async/worker-executions")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["active_worker_execution"] == "none"
    assert body["worker_count"] == 3
    assert body["workers"][0]["worker_id"] == "none"
    assert body["workers"][1]["worker_id"] == "in_process_stub"
    assert body["workers"][2]["worker_id"] == "queue_backed_workers"


def test_async_activation_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/async/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["activation_ready"] is False
    assert body["queue_backend"] == "none"
    assert body["worker_execution"] == "none"
    assert body["supported_job_type_count"] == 3
    assert len(body["blocking_findings"]) == 4
    assert len(body["activation_path"]) == 4


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
    assert body["queued_job_count"] == 1
    assert body["jobs"][0]["job_id"] == "asyncjob_retrieval_indexing_001"
    assert body["jobs"][1]["status"] == "SUPERSEDED"
    assert body["jobs"][1]["related_evaluation_run_id"] == "foundation_eval_2026_03_21_001"


def test_async_job_detail_route(client: TestClient) -> None:
    response = client.get("/platform/async/jobs/asyncjob_retrieval_indexing_001")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["job"]["job_type"] == "retrieval_indexing"
    assert body["job"]["status"] == "QUEUED"
    assert body["job"]["related_evaluation_run_id"] is None


def test_async_job_detail_route_returns_not_found_for_unknown_job(client: TestClient) -> None:
    response = client.get("/platform/async/jobs/missing_async_job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Async job artifact 'missing_async_job' was not found."


def test_async_job_submit_route_returns_rejected_contract_response(client: TestClient) -> None:
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
    assert body["submission_status"] == "REJECTED"
    assert body["accepted"] is False
    assert body["job_id"] is None
    assert body["queue_mode"] == "DISABLED"


def test_async_runtime_status_route_reports_stubbed_runtime_when_enabled(
    client: TestClient,
) -> None:
    settings.async_queue_mode = "stubbed"
    settings.async_worker_mode = "stubbed"

    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["queue_mode"] == "STUBBED"
    assert body["worker_mode"] == "STUBBED"
    assert body["active_worker_execution"] == "in_process_stub"
    assert body["active_worker_count"] == 1
    assert any(
        job["job_type"] == "retrieval_indexing" and job["enabled"] is True
        for job in body["supported_job_types"]
    )


def test_async_job_submit_route_accepts_stubbed_retrieval_indexing(client: TestClient) -> None:
    settings.async_queue_mode = "stubbed"
    settings.async_worker_mode = "stubbed"

    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-003",
            "target_id": "retjob_lotus_platform_rfcs",
            "payload_summary": "Replay approved RFC retrieval indexing.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission_status"] == "ACCEPTED"
    assert body["accepted"] is True
    assert body["job_id"] is not None
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
