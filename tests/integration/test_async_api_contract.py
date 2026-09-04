from _pytest.monkeypatch import MonkeyPatch
from app.services.async_worker_runtime import (
    claim_next_async_job,
    complete_async_job,
    start_async_job,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.config import settings
from app.services.async_delivery_queue import get_test_async_delivery_queue
from app.services.async_runtime_store import get_async_runtime_store
from app.services.eval_async_execution import run_next_evaluation_execution_job
from fastapi.testclient import TestClient


def test_async_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["cutover_state"] == "in_process_only"
    assert body["queue_mode"] == "DISABLED"
    assert body["worker_mode"] == "IN_PROCESS_ONLY"
    assert body["queue_backend"] == "none"
    assert body["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["supported_queue_backends"][1]["backend_id"] == "redis_queue"
    assert body["active_worker_execution"] == "in_process_stub"
    assert body["supported_worker_executions"][0]["worker_id"] == "none"
    assert body["supported_worker_executions"][2]["worker_id"] == "queue_backed_workers"
    assert body["active_worker_count"] == 0
    assert body["active_worker_ids"] == []
    assert body["enqueued_job_count"] == 0
    assert body["recorded_job_count"] == 2
    assert body["queue_backlog_count"] == 0
    assert body["duplicate_delivery_count"] == 0
    assert body["redelivery_count"] == 0
    assert body["drain_mode_active"] is False
    assert body["degraded_findings"] == []
    assert body["supported_job_types"][0]["enabled"] is True
    assert body["supported_job_types"][0]["execution_path"] == "durable_runtime_worker_execution"
    assert any(job["job_type"] == "retrieval_indexing" for job in body["supported_job_types"])


def test_async_runtime_status_route_reports_dedicated_worker_cutover(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_operational_state.get_async_delivery_queue", lambda: queue
    )

    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["cutover_state"] == "dedicated_workers_active"
    assert body["queue_mode"] == "ACTIVE"
    assert body["worker_mode"] == "DEDICATED"
    assert body["queue_backend"] == "redis_queue"
    assert body["active_worker_execution"] == "queue_backed_workers"
    assert body["queue_backlog_count"] == 0
    assert body["degraded_findings"] == []


def test_async_runtime_status_route_flags_queued_job_without_delivery(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_operational_state.get_async_delivery_queue",
        lambda: queue,
    )
    _persist_queued_async_job(job_id="asyncjob_stranded_status")

    response = client.get("/platform/async/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["enqueued_job_count"] == 1
    assert body["queue_backlog_count"] == 0
    assert any(
        "Queued async runtime jobs exist without pending managed-queue deliveries" in finding
        for finding in body["degraded_findings"]
    )


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
    assert body["cutover_state"] == "in_process_only"
    assert body["queue_backend"] == "none"
    assert body["worker_execution"] == "in_process_stub"
    assert body["supported_job_type_count"] == 4
    assert len(body["blocking_findings"]) == 2
    assert len(body["activation_path"]) == 2


def test_async_activation_readiness_route_reports_shadow_cutover(client: TestClient) -> None:
    settings.async_cutover_state = "queue_delivery_shadow"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    response = client.get("/platform/async/activation-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["cutover_state"] == "queue_delivery_shadow"
    assert body["queue_backend"] == "redis_queue"
    assert body["worker_execution"] == "in_process_stub"


def test_async_runbook_readiness_route(client: TestClient) -> None:
    response = client.get("/platform/async/runbook-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["runbook_ready"] is False
    assert body["required_item_count"] == 4
    # Honest catalog vocabulary (issue #284): documented posture is
    # DOCUMENTED_ONLY, an unwritten runbook is MISSING - nothing completes
    # until a control is enforced.
    assert body["completed_required_item_count"] == 0
    assert body["items"][0]["runbook_id"] == "async_operational_runbook"
    assert body["items"][0]["status"] == "DOCUMENTED_ONLY"
    assert body["items"][1]["status"] == "MISSING"


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


def test_async_governance_status_route_reports_degraded_fallback(client: TestClient) -> None:
    settings.async_cutover_state = "degraded_fallback"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    response = client.get("/platform/async/governance-status")

    assert response.status_code == 200
    body = response.json()
    assert body["activation_readiness"]["cutover_state"] == "degraded_fallback"
    assert "degraded fallback posture" in body["governance_summary"][0]


def test_async_control_history_route(client: TestClient) -> None:
    response = client.get("/platform/async/control-plane-actions")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["supported_action_types"][0] == "RETRY_FAILED_JOB"


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
    assert body["jobs"][0]["target_id"] is None
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
    assert body["control_events"] == []


def test_async_job_detail_route_returns_not_found_for_unknown_job(client: TestClient) -> None:
    response = client.get("/platform/async/jobs/missing_async_job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Async job artifact 'missing_async_job' was not found."


def test_async_job_submit_route_accepts_runtime_backed_submission(client: TestClient) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "target_id": "retjob_lotus_platform_rfcs",
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
    assert body["target_id"] == "retjob_lotus_platform_rfcs"
    assert body["existing_job_id"] is None
    assert body["cutover_state"] == "in_process_only"
    assert body["queue_mode"] == "DISABLED"
    assert body["worker_mode"] == "IN_PROCESS_ONLY"

    catalog_response = client.get("/platform/async/jobs")
    catalog_body = catalog_response.json()
    runtime_job = next(job for job in catalog_body["jobs"] if job["job_id"] == body["job_id"])

    assert catalog_body["queued_job_count"] == 1
    assert runtime_job["status"] == "QUEUED"
    assert runtime_job["record_source"] == "RUNTIME_STATE"
    assert runtime_job["target_id"] == "retjob_lotus_platform_rfcs"


def test_async_job_detail_route_exposes_runtime_attempt_and_lease_history(
    client: TestClient,
) -> None:
    submit_response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "target_id": "retjob_lotus_platform_rfcs",
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
    assert len(completed_body["job"]["artifact_refs"]) == 1


def test_async_job_submit_route_rejects_duplicate_active_runtime_submission(
    client: TestClient,
) -> None:
    first = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "target_id": "retjob_lotus_platform_rfcs",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-duplicate-001",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )

    duplicate = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "target_id": "retjob_lotus_platform_rfcs",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-duplicate-002",
            "payload_summary": "Index newly approved RFC documents again.",
        },
    )

    assert first.status_code == 200
    assert duplicate.status_code == 200
    duplicate_body = duplicate.json()
    assert duplicate_body["submission_status"] == "DUPLICATE_REJECTED"
    assert duplicate_body["accepted"] is False
    assert duplicate_body["existing_job_id"] == first.json()["job_id"]


def test_async_control_action_route_records_manual_replay_event(client: TestClient) -> None:
    submit_response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "target_id": "retjob_lotus_platform_rfcs",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-replay-001",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )
    job_id = submit_response.json()["job_id"]
    claim_next_async_job(worker_id="worker-a")
    start_async_job(job_id=job_id, worker_id="worker-a")
    complete_async_job(
        job_id=job_id,
        worker_id="worker-a",
        message="Retrieval indexing completed successfully.",
    )

    action_response = client.post(
        "/platform/async/control-plane-actions/apply",
        json={
            "job_id": job_id,
            "action_type": "REPLAY_TERMINAL_JOB",
            "caller_app": "lotus-platform",
            "requested_by": "operator-a",
            "approved_by": "approver-a",
            "reason": "Replay completed job for verification.",
        },
    )

    assert action_response.status_code == 200
    action_body = action_response.json()
    assert action_body["event"]["action_type"] == "REPLAY_TERMINAL_JOB"
    assert action_body["event"]["prior_status"] == "COMPLETED"
    assert action_body["event"]["resulting_status"] == "QUEUED"
    assert action_body["event"]["authorization"]["caller_app"] == "lotus-platform"

    detail_response = client.get(f"/platform/async/jobs/{job_id}")
    detail_body = detail_response.json()
    assert detail_body["job"]["status"] == "QUEUED"
    assert detail_body["control_events"][0]["action_type"] == "REPLAY_TERMINAL_JOB"


def test_async_control_action_route_redrives_stranded_queued_job(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    _persist_queued_async_job(job_id="asyncjob_redrive_control")

    action_response = client.post(
        "/platform/async/control-plane-actions/apply",
        json={
            "job_id": "asyncjob_redrive_control",
            "action_type": "REDRIVE_QUEUED_JOB",
            "caller_app": "lotus-platform",
            "requested_by": "operator-a",
            "approved_by": "approver-a",
            "reason": "Re-drive queued job after missing managed queue delivery.",
        },
    )

    assert action_response.status_code == 200
    body = action_response.json()
    assert body["event"]["action_type"] == "REDRIVE_QUEUED_JOB"
    assert body["event"]["prior_status"] == "QUEUED"
    assert body["event"]["resulting_status"] == "QUEUED"
    assert queue.snapshot().pending_delivery_count == 1


def test_async_control_action_route_quarantines_stranded_queued_job(
    client: TestClient,
) -> None:
    _persist_queued_async_job(job_id="asyncjob_quarantine_control")

    action_response = client.post(
        "/platform/async/control-plane-actions/apply",
        json={
            "job_id": "asyncjob_quarantine_control",
            "action_type": "QUARANTINE_QUEUED_JOB",
            "caller_app": "lotus-platform",
            "requested_by": "operator-a",
            "approved_by": "approver-a",
            "reason": "Quarantine queued job after missing managed queue delivery.",
        },
    )
    detail_response = client.get("/platform/async/jobs/asyncjob_quarantine_control")

    assert action_response.status_code == 200
    assert action_response.json()["event"]["action_type"] == "QUARANTINE_QUEUED_JOB"
    assert action_response.json()["event"]["prior_status"] == "QUEUED"
    assert action_response.json()["event"]["resulting_status"] == "ABANDONED"
    assert detail_response.status_code == 200
    assert detail_response.json()["job"]["status"] == "ABANDONED"
    assert detail_response.json()["attempts"][0]["failure_reason"] == "DELIVERY_QUARANTINED"


def test_async_job_submit_route_rejects_documentation_only_job_type(client: TestClient) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "evaluation_execution",
            "target_id": "provider_runtime_examples",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-001-eval",
            "payload_summary": "Run staged evaluation family.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission_status"] == "ACCEPTED"
    assert body["accepted"] is True
    assert body["job_id"] is not None
    assert body["cutover_state"] == "in_process_only"
    assert body["queue_mode"] == "DISABLED"
    assert body["worker_mode"] == "IN_PROCESS_ONLY"


def test_async_control_action_route_blocks_unauthorized_caller(client: TestClient) -> None:
    submit_response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "target_id": "retjob_lotus_platform_rfcs",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-replay-unauthorized",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )
    job_id = submit_response.json()["job_id"]

    action_response = client.post(
        "/platform/async/control-plane-actions/apply",
        json={
            "job_id": job_id,
            "action_type": "REPLAY_TERMINAL_JOB",
            "caller_app": "lotus-workbench",
            "requested_by": "operator-a",
            "approved_by": "approver-a",
            "reason": "Unauthorized replay attempt.",
        },
    )

    assert action_response.status_code == 403


def test_async_job_detail_route_exposes_runtime_backed_evaluation_execution(
    client: TestClient,
) -> None:
    submission = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "evaluation_execution",
            "target_id": "provider_policy_examples",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-001-eval-run",
            "payload_summary": "Run provider policy evaluation family.",
        },
    ).json()

    run_next_evaluation_execution_job(worker_id="worker-a")

    detail_response = client.get(f"/platform/async/jobs/{submission['job_id']}")

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["job"]["job_type"] == "evaluation_execution"
    assert body["job"]["status"] == "COMPLETED"
    assert body["job"]["related_evaluation_run_id"] is not None
    assert body["attempts"][0]["status"] == "COMPLETED"
    assert len(body["job"]["artifact_refs"]) == 1


def test_async_job_submit_route_rejects_missing_retrieval_target_id(client: TestClient) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "retrieval_indexing",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-async-submit-missing-target",
            "payload_summary": "Index newly approved RFC documents.",
        },
    )

    assert response.status_code == 409
    assert "requires a concrete retrieval index job target_id" in response.json()["detail"]


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


def _persist_queued_async_job(*, job_id: str) -> None:
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job_id,
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="QUEUED",
            submitted_at="2026-03-24T00:00:00Z",
            caller_app="lotus-platform",
            correlation_id=f"corr-{job_id}",
            payload_summary="Queued job for async recovery contract test.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued job awaiting managed delivery.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=f"{job_id}_attempt_001",
            job_id=job_id,
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Queued job awaiting managed delivery.",
        )
    )
