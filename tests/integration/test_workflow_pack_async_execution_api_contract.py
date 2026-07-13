from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.artifact_payloads import persist_json_artifact
from app.services.async_delivery_queue import get_test_async_delivery_queue
from app.services.async_worker_fleet import process_next_async_delivery
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_store import get_async_runtime_store
from app.services.artifact_store import get_artifact_object_store
from app.services.artifact_store import get_artifact_repository
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.workflow_pack_queue_event_store import get_workflow_pack_queue_event_store
from app.services.workflow_pack_async_execution import (
    _enforce_queued_capacity,
    _load_first_snapshot_for_job,
    _reject_duplicate_active_submission,
    _record_queue_event,
    _transition,
    run_next_workflow_pack_execution_job,
    run_workflow_pack_execution_job_by_id,
)
from app.services.workflow_pack_queue_policy_catalog import (
    get_workflow_pack_queue_policy_descriptor,
)
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.workflow_pack_fixtures import (
    advisor_brief_workflow_pack_execution_request_json,
)


def test_workflow_pack_async_execution_route_persists_queue_snapshot_and_job(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-api-001"
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["queue_item_id"].startswith("wpq_")
    assert body["async_job"]["job_type"] == "workflow_pack_execution"
    assert body["async_job"]["target_id"] == body["queue_item_id"]
    assert body["async_job"]["status"] == "QUEUED"
    assert body["async_job"]["artifact_refs"][0]["artifact_type"] == "queue_request_snapshot"
    assert body["queue_event"]["event_type"] == "ADMISSION_QUEUED"
    assert body["queue_event"]["queue_item_id"] == body["queue_item_id"]
    assert body["queue_event"]["artifact_refs"] == body["async_job"]["artifact_refs"]
    assert any("durable async runtime job" in line for line in body["status_summary"])

    detail_response = client.get(f"/platform/workflow-packs/queue-events/{body['queue_item_id']}")

    assert detail_response.status_code == 200
    assert [event["event_type"] for event in detail_response.json()["events"]] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
    ]


def test_workflow_pack_async_execution_rejects_generic_async_submit(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/async/jobs/submit",
        json={
            "job_type": "workflow_pack_execution",
            "target_id": "wpq_missing",
            "caller_app": "lotus-gateway",
            "correlation_id": "corr-workflow-pack-generic-async-rejected",
            "payload_summary": "Attempt to bypass workflow-pack async submission.",
        },
    )

    assert response.status_code == 409
    assert "/platform/workflow-packs/execute-async" in response.json()["detail"]


def test_workflow_pack_async_execution_rejects_unknown_pack(
    client: TestClient,
) -> None:
    request = advisor_brief_workflow_pack_execution_request_json(
        correlation_id="corr-workflow-pack-async-unknown-pack-001"
    )
    request["pack_id"] = "missing.pack"

    response = client.post("/platform/workflow-packs/execute-async", json=request)

    assert response.status_code == 404
    assert "Unknown workflow-pack registration" in response.json()["detail"]


def test_workflow_pack_async_execution_rejects_denied_eligibility(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.evaluate_workflow_pack_eligibility",
        lambda request: SimpleNamespace(allowed=False, denial_reasons=["caller denied"]),
    )

    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-denied-001"
        ),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "caller denied"


def test_workflow_pack_async_execution_rejects_missing_policy(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.get_workflow_pack_queue_policy_descriptor",
        lambda *, pack_id, version: None,
    )

    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-missing-policy-001"
        ),
    )

    assert response.status_code == 409
    assert "queue policy is not declared" in response.json()["detail"]


def test_workflow_pack_async_execution_preflights_queue_event_store_before_side_effects(
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
    monkeypatch.setattr(
        "app.services.workflow_pack_queue_events.get_workflow_pack_queue_event_store_runtime_status",
        lambda: StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=RuntimeReadinessStatus.MIGRATION_REQUIRED,
            database_configured=True,
            detail="Configured database is reachable but missing required tables: workflow_pack_queue_events.",
        ),
    )

    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-queue-store-not-ready-001"
        ),
    )

    assert response.status_code == 503
    assert "Workflow-pack queue event store is not ready:" in response.json()["detail"]
    assert get_artifact_repository().list_artifacts() == []
    assert get_workflow_pack_queue_event_store().list_events() == []
    assert get_async_runtime_store().list_jobs() == []
    assert queue.snapshot().pending_delivery_count == 0
    assert queue.snapshot().published_delivery_count == 0


def test_workflow_pack_async_execution_rejects_unsupported_lane(
    client: TestClient,
) -> None:
    request = advisor_brief_workflow_pack_execution_request_json(
        correlation_id="corr-workflow-pack-async-unsupported-lane-001"
    )
    request["queue_lane"] = "BATCH"

    response = client.post("/platform/workflow-packs/execute-async", json=request)

    assert response.status_code == 409
    assert "queue lane `BATCH` is not allowed" in response.json()["detail"]


def test_workflow_pack_async_execution_rejects_duplicate_active_correlation(
    client: TestClient,
) -> None:
    request = advisor_brief_workflow_pack_execution_request_json(
        correlation_id="corr-workflow-pack-async-duplicate-001"
    )

    first_response = client.post("/platform/workflow-packs/execute-async", json=request)
    second_response = client.post("/platform/workflow-packs/execute-async", json=request)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert "already owns correlation id" in second_response.json()["detail"]


def test_workflow_pack_async_execution_enforces_persisted_queue_capacity(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    from app.services.workflow_pack_queue_policy_catalog import (
        get_workflow_pack_queue_policy_descriptor,
    )

    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )
    assert policy is not None
    saturated_policy = policy.model_copy(
        update={
            "max_queued_runs_per_pack": 1,
            "max_queued_runs_per_lane": 1,
        },
        deep=True,
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.get_workflow_pack_queue_policy_descriptor",
        lambda *, pack_id, version: (
            saturated_policy if pack_id == "advisor_brief.pack" and version == "v1" else None
        ),
    )

    first_response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-capacity-001"
        ),
    )
    second_response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-capacity-002"
        ),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert "max_queued_runs_per_pack" in second_response.json()["detail"]


def test_workflow_pack_async_execution_worker_noops_when_no_job_is_available() -> None:
    assert run_next_workflow_pack_execution_job(worker_id="worker-a") is None


def test_workflow_pack_async_execution_run_by_id_noops_when_job_is_unavailable() -> None:
    assert (
        run_workflow_pack_execution_job_by_id(
            async_job_id="missing-workflow-pack-async-job",
            worker_id="worker-a",
        )
        is None
    )


def test_workflow_pack_async_execution_run_next_completes_without_delivery_queue(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-run-next-001"
        ),
    )
    assert response.status_code == 200

    result = run_next_workflow_pack_execution_job(worker_id="worker-a")

    assert result is not None
    assert result.async_job_id == response.json()["async_job"]["job_id"]
    assert result.terminal_status == "COMPLETED"


def test_workflow_pack_async_execution_worker_fails_unsupported_claimed_job() -> None:
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-workflow-pack-unsupported",
            job_type="unsupported_workflow_pack_worker_type",
            target_id="wpq_unsupported",
            lifecycle_status="QUEUED",
            submitted_at="2026-04-22T00:00:00Z",
            caller_app="lotus-gateway",
            correlation_id="corr-workflow-pack-async-unsupported-claim",
            payload_summary="Unsupported workflow-pack async worker type.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued unsupported workflow-pack worker job.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="async-job-workflow-pack-unsupported_attempt_001",
            job_id="async-job-workflow-pack-unsupported",
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Queued.",
        )
    )

    result = run_workflow_pack_execution_job_by_id(
        async_job_id="async-job-workflow-pack-unsupported",
        worker_id="worker-a",
    )
    detail = build_async_job_detail(job_id="async-job-workflow-pack-unsupported")

    assert result is not None
    assert result.terminal_status == "FAILED"
    assert detail.job.status.value == "FAILED"
    assert detail.attempts[0].failure_reason == "UNSUPPORTED_ASYNC_JOB_TYPE"


def test_workflow_pack_async_execution_worker_fails_missing_queue_event(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-missing-event-001"
        ),
    )
    assert response.status_code == 200
    job_id = response.json()["async_job"]["job_id"]
    monkeypatch.setattr(
        "app.services.workflow_pack_queue_events.build_workflow_pack_queue_event_detail",
        lambda *, queue_item_id: SimpleNamespace(events=[]),
    )

    result = run_workflow_pack_execution_job_by_id(
        async_job_id=job_id,
        worker_id="worker-a",
    )
    async_detail = build_async_job_detail(job_id=job_id)

    assert result is not None
    assert result.terminal_status == "FAILED"
    assert async_detail.job.status.value == "FAILED"
    assert async_detail.active_lease is None
    assert async_detail.attempts[0].failure_reason == "HTTPException"


def test_workflow_pack_async_execution_worker_degrades_missing_policy_after_claim(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-worker-missing-policy-001"
        ),
    )
    assert response.status_code == 200
    body = response.json()
    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.get_workflow_pack_queue_policy_descriptor",
        lambda *, pack_id, version: None,
    )

    result = run_workflow_pack_execution_job_by_id(
        async_job_id=body["async_job"]["job_id"],
        worker_id="worker-a",
    )
    async_detail = build_async_job_detail(job_id=body["async_job"]["job_id"])
    queue_detail_response = client.get(
        f"/platform/workflow-packs/queue-events/{body['queue_item_id']}"
    )

    assert result is not None
    assert result.terminal_status == "FAILED"
    assert async_detail.job.status.value == "FAILED"
    assert queue_detail_response.json()["events"][-1]["event_type"] == "ADMISSION_DEGRADED"
    assert queue_detail_response.json()["events"][-1]["reason_code"] == "QUEUE_POLICY_NOT_FOUND"


def test_workflow_pack_async_execution_worker_degrades_execution_conflict(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-execution-conflict-001"
        ),
    )
    assert response.status_code == 200
    body = response.json()
    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.execute_workflow_pack",
        lambda request: (_ for _ in ()).throw(HTTPException(status_code=409, detail="conflict")),
    )

    result = run_workflow_pack_execution_job_by_id(
        async_job_id=body["async_job"]["job_id"],
        worker_id="worker-a",
    )
    async_detail = build_async_job_detail(job_id=body["async_job"]["job_id"])
    queue_detail_response = client.get(
        f"/platform/workflow-packs/queue-events/{body['queue_item_id']}"
    )

    assert result is not None
    assert result.terminal_status == "FAILED"
    assert async_detail.job.status.value == "FAILED"
    assert [event["event_type"] for event in queue_detail_response.json()["events"]] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
        "ADMISSION_ADMITTED",
        "ADMISSION_GRANTED",
        "ADMISSION_DEGRADED",
    ]
    assert queue_detail_response.json()["events"][-1]["reason_code"] == "HTTPException"


def test_workflow_pack_async_execution_worker_reraises_unexpected_execution_error(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-execution-error-001"
        ),
    )
    assert response.status_code == 200
    body = response.json()
    monkeypatch.setattr(
        "app.services.workflow_pack_async_execution.execute_workflow_pack",
        lambda request: (_ for _ in ()).throw(RuntimeError("unexpected worker failure")),
    )

    try:
        run_workflow_pack_execution_job_by_id(
            async_job_id=body["async_job"]["job_id"],
            worker_id="worker-a",
        )
    except RuntimeError as exc:
        assert "unexpected worker failure" in str(exc)
    else:
        raise AssertionError("Expected unexpected worker errors to propagate.")

    async_detail = build_async_job_detail(job_id=body["async_job"]["job_id"])
    queue_detail_response = client.get(
        f"/platform/workflow-packs/queue-events/{body['queue_item_id']}"
    )

    assert async_detail.job.status.value == "FAILED"
    assert queue_detail_response.json()["events"][-1]["event_type"] == "ADMISSION_DEGRADED"
    assert queue_detail_response.json()["events"][-1]["reason_code"] == "RuntimeError"


def test_workflow_pack_async_execution_capacity_uses_matching_snapshot_identity(
    client: TestClient,
) -> None:
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )
    assert policy is not None

    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-unrelated-capacity",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="QUEUED",
            submitted_at="2026-04-22T00:00:00Z",
            caller_app="lotus-platform",
            correlation_id="corr-unrelated-capacity",
            payload_summary="Unrelated queued async job.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued unrelated job.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-workflow-pack-no-snapshot-capacity",
            job_type="workflow_pack_execution",
            target_id="wpq_no_snapshot_capacity",
            lifecycle_status="QUEUED",
            submitted_at="2026-04-22T00:00:00Z",
            caller_app="lotus-gateway",
            correlation_id="corr-no-snapshot-capacity",
            payload_summary="Workflow-pack queued job without retained snapshot.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-capacity-identity-001"
        ),
    )
    assert response.status_code == 200

    _enforce_queued_capacity(
        policy=policy.model_copy(update={"workflow_pack_id": "workspace_rationale.pack"}),
        lane=WorkflowPackQueueLane.REVIEW_SUPPORT,
    )
    _enforce_queued_capacity(
        policy=policy.model_copy(update={"workflow_pack_version": "v2"}),
        lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
    )
    lane_saturated_policy = policy.model_copy(
        update={
            "max_queued_runs_per_pack": 2,
            "max_queued_runs_per_lane": 1,
        }
    )

    try:
        _enforce_queued_capacity(
            policy=lane_saturated_policy,
            lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
        )
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "max_queued_runs_per_lane" in exc.detail
    else:
        raise AssertionError("Expected lane capacity saturation to reject admission.")


def test_workflow_pack_async_execution_duplicate_check_uses_snapshot_identity(
    client: TestClient,
) -> None:
    request = advisor_brief_workflow_pack_execution_request_json(
        correlation_id="corr-workflow-pack-async-duplicate-identity-001"
    )
    response = client.post("/platform/workflow-packs/execute-async", json=request)
    assert response.status_code == 200
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )
    assert policy is not None
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-workflow-pack-no-snapshot-duplicate",
            job_type="workflow_pack_execution",
            target_id="wpq_no_snapshot_duplicate",
            lifecycle_status="QUEUED",
            submitted_at="2026-04-22T00:00:00Z",
            caller_app="lotus-gateway",
            correlation_id="corr-workflow-pack-async-duplicate-identity-001",
            payload_summary="Workflow-pack queued job without retained snapshot.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    parsed_request = WorkflowPackExecutionRequest.model_validate(request)

    _reject_duplicate_active_submission(
        request=parsed_request,
        policy=policy.model_copy(update={"workflow_pack_id": "workspace_rationale.pack"}),
    )
    _reject_duplicate_active_submission(
        request=parsed_request,
        policy=policy.model_copy(update={"workflow_pack_version": "v2"}),
    )


def test_workflow_pack_async_execution_ignores_non_snapshot_artifacts() -> None:
    artifact = persist_json_artifact(
        domain="workflow-pack-queue",
        artifact_type="operator_note",
        source_object_kind="workflow_pack_queue_item",
        source_object_id="wpq_non_snapshot",
        created_at="2026-04-22T00:00:00Z",
        created_by="test",
        payload_json=b'{"note": "not executable input"}',
    )
    job = AsyncRuntimeJobRecord(
        job_id="async-job-non-snapshot-artifact",
        job_type="workflow_pack_execution",
        target_id="wpq_non_snapshot",
        lifecycle_status="QUEUED",
        submitted_at="2026-04-22T00:00:00Z",
        caller_app="lotus-gateway",
        correlation_id="corr-non-snapshot-artifact",
        payload_summary="Queued job with non-snapshot artifact.",
        execution_path="durable_runtime_worker_execution",
        related_evaluation_run_id=None,
        latest_message="Queued.",
        attempt_count=1,
        artifact_ids=[artifact.artifact_id],
    )

    assert _load_first_snapshot_for_job(job=job) is None


def test_workflow_pack_async_execution_rejects_invalid_internal_transitions() -> None:
    try:
        _transition(
            current_state=WorkflowPackQueueState.COMPLETED_HANDOFF,
            next_state=WorkflowPackQueueState.QUEUED,
        )
    except RuntimeError as exc:
        assert "Illegal workflow-pack queue transition" in str(exc)
    else:
        raise AssertionError("Expected invalid queue transition to fail.")


def test_workflow_pack_async_execution_requires_event_identity() -> None:
    try:
        _record_queue_event(
            queue_item_id="wpq_missing_identity",
            event_type=WorkflowPackQueueEventType.ADMISSION_DEGRADED,
            state=WorkflowPackQueueState.DEGRADED,
            message="missing identity",
        )
    except RuntimeError as exc:
        assert "queue event identity is required" in str(exc)
    else:
        raise AssertionError("Expected missing queue event identity to fail.")


def test_workflow_pack_async_execution_dedicated_worker_produces_run(
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
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-worker-001"
        ),
    )
    assert response.status_code == 200
    job_id = response.json()["async_job"]["job_id"]
    queue_item_id = response.json()["queue_item_id"]

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    async_detail = build_async_job_detail(job_id=job_id)
    queue_detail_response = client.get(f"/platform/workflow-packs/queue-events/{queue_item_id}")
    run_catalog_response = client.get(
        "/platform/workflow-packs/runs",
        params={"caller_app": "lotus-gateway"},
    )

    assert result is not None
    assert result.job_id == job_id
    assert result.job_type == "workflow_pack_execution"
    assert result.handled is True
    assert result.terminal_status == "COMPLETED"
    assert async_detail.job.status.value == "COMPLETED"
    assert async_detail.active_lease is None
    assert len(async_detail.attempts) == 1
    assert async_detail.attempts[0].status == "COMPLETED"
    assert queue_detail_response.status_code == 200
    assert [event["event_type"] for event in queue_detail_response.json()["events"]] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
        "ADMISSION_ADMITTED",
        "ADMISSION_GRANTED",
        "ADMISSION_RELEASED",
    ]
    assert run_catalog_response.status_code == 200
    assert run_catalog_response.json()["run_count"] == 1
    assert run_catalog_response.json()["runs"][0]["registration_ref"] == "advisor_brief.pack@v1"


def test_workflow_pack_async_execution_worker_degrades_corrupt_snapshot(
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
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-corrupt-snapshot-001"
        ),
    )
    assert response.status_code == 200
    body = response.json()
    job_id = body["async_job"]["job_id"]
    queue_item_id = body["queue_item_id"]
    object_key = body["async_job"]["artifact_refs"][0]["storage_reference"].partition("://")[2]
    get_artifact_object_store().delete_object(object_key=object_key)

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    async_detail = build_async_job_detail(job_id=job_id)
    queue_detail_response = client.get(f"/platform/workflow-packs/queue-events/{queue_item_id}")

    assert result is not None
    assert result.handled is True
    assert result.terminal_status == "FAILED"
    assert async_detail.job.status.value == "FAILED"
    assert async_detail.active_lease is None
    assert async_detail.attempts[0].failure_reason == "ValueError"
    assert [event["event_type"] for event in queue_detail_response.json()["events"]] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
        "ADMISSION_DEGRADED",
    ]
    assert queue_detail_response.json()["events"][-1]["reason_code"] == "ValueError"


def test_workflow_pack_async_execution_survives_sql_async_store_restart(
    tmp_path: Path,
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'workflow-pack-async-worker.db'}"
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    upgrade_database_to_head(settings.database_url)
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    response = client.post(
        "/platform/workflow-packs/execute-async",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-workflow-pack-async-sql-001"
        ),
    )
    assert response.status_code == 200
    job_id = response.json()["async_job"]["job_id"]
    reset_async_runtime_store_cache()

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    async_detail = build_async_job_detail(job_id=job_id)

    assert result is not None
    assert result.terminal_status == "COMPLETED"
    assert async_detail.job.status.value == "COMPLETED"
