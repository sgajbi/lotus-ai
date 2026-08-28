from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from fastapi import HTTPException
import pytest

from app.contracts.workflow_packs import (
    WorkflowPackExecutionIdempotencyStatus,
    WorkflowPackExecutionRequest,
    WorkflowPackExecutionResponse,
)
from app.services.workflow_pack_execution import execute_workflow_pack
from app.workflow_pack_execution_idempotency.memory_repository import (
    InMemoryWorkflowPackExecutionIdempotencyRepository,
)
from app.workflow_pack_execution_idempotency.repository import (
    WorkflowPackExecutionIdempotencyRecord,
    WorkflowPackExecutionIdempotencyState,
)
from app.workflow_pack_execution_idempotency.service import (
    build_workflow_pack_execution_idempotency_record_id,
    execute_workflow_pack_idempotently,
    fingerprint_workflow_pack_execution_request,
)
from tests.support.workflow_pack_fixtures import (
    advisor_brief_workflow_pack_execution_request_json,
)


def test_same_key_same_input_replays_original_execution_without_calling_executor_again() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    request = _request(idempotency_key="advisor-memo-001")
    calls = 0

    def counting_executor(value: WorkflowPackExecutionRequest) -> WorkflowPackExecutionResponse:
        nonlocal calls
        calls += 1
        return execute_workflow_pack(value)

    created = execute_workflow_pack_idempotently(
        request,
        execute=counting_executor,
        repository=repository,
        owner_token="owner-created",
        now=lambda: "2026-08-28T01:00:00Z",
    )
    replayed = execute_workflow_pack_idempotently(
        request,
        execute=counting_executor,
        repository=repository,
        owner_token="owner-retry",
        now=lambda: "2026-08-28T01:01:00Z",
    )

    assert calls == 1
    assert created.idempotency is not None
    assert created.idempotency.status is WorkflowPackExecutionIdempotencyStatus.CREATED
    assert replayed.idempotency is not None
    assert replayed.idempotency.status is WorkflowPackExecutionIdempotencyStatus.REPLAYED
    assert replayed.execution.audit.request_id == created.execution.audit.request_id
    assert replayed.workflow_pack_run.run_id == created.workflow_pack_run.run_id
    assert replayed.execution.result == created.execution.result


def test_same_key_different_input_conflicts_before_executor_call() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    calls = 0

    def counting_executor(value: WorkflowPackExecutionRequest) -> WorkflowPackExecutionResponse:
        nonlocal calls
        calls += 1
        return execute_workflow_pack(value)

    execute_workflow_pack_idempotently(
        _request(idempotency_key="advisor-memo-002", correlation_id="corr-original"),
        execute=counting_executor,
        repository=repository,
    )

    with pytest.raises(HTTPException) as caught:
        execute_workflow_pack_idempotently(
            _request(idempotency_key="advisor-memo-002", correlation_id="corr-changed"),
            execute=counting_executor,
            repository=repository,
        )

    assert caught.value.status_code == 409
    assert "workflow_pack_execution_idempotency_conflict" in str(caught.value.detail)
    assert calls == 1


def test_concurrent_same_key_request_is_explicitly_in_progress_without_duplicate_execution() -> (
    None
):
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    request = _request(idempotency_key="advisor-memo-003")
    executor_entered = Event()
    release_executor = Event()
    call_lock = Lock()
    calls = 0

    def blocking_executor(value: WorkflowPackExecutionRequest) -> WorkflowPackExecutionResponse:
        nonlocal calls
        with call_lock:
            calls += 1
        executor_entered.set()
        assert release_executor.wait(timeout=5)
        return execute_workflow_pack(value)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            execute_workflow_pack_idempotently,
            request,
            execute=blocking_executor,
            repository=repository,
            owner_token="owner-first",
        )
        assert executor_entered.wait(timeout=5)
        with pytest.raises(HTTPException) as caught:
            execute_workflow_pack_idempotently(
                request,
                execute=blocking_executor,
                repository=repository,
                owner_token="owner-second",
            )
        release_executor.set()
        completed = first.result(timeout=5)

    assert caught.value.status_code == 409
    assert "workflow_pack_execution_idempotency_in_progress" in str(caught.value.detail)
    assert completed.idempotency is not None
    assert completed.idempotency.status is WorkflowPackExecutionIdempotencyStatus.CREATED
    assert calls == 1


def test_uncertain_execution_is_retained_and_blocks_automatic_retry() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    request = _request(idempotency_key="advisor-memo-004")

    def failed_executor(_: WorkflowPackExecutionRequest) -> WorkflowPackExecutionResponse:
        raise RuntimeError("simulated persistence boundary failure")

    with pytest.raises(RuntimeError):
        execute_workflow_pack_idempotently(
            request,
            execute=failed_executor,
            repository=repository,
            owner_token="owner-failed",
            now=lambda: "2026-08-28T01:00:00Z",
        )

    record_id = build_workflow_pack_execution_idempotency_record_id(
        caller_app=request.task_request.caller.caller_app,
        tenant_id=request.task_request.caller.tenant_id,
        idempotency_key="advisor-memo-004",
    )
    record = repository.get(record_id=record_id)
    assert record is not None
    assert record.state is WorkflowPackExecutionIdempotencyState.INDETERMINATE

    with pytest.raises(HTTPException) as caught:
        execute_workflow_pack_idempotently(
            request,
            execute=execute_workflow_pack,
            repository=repository,
        )
    assert caught.value.status_code == 409
    assert "workflow_pack_execution_idempotency_outcome_indeterminate" in str(caught.value.detail)


def test_corrupted_retained_response_is_not_replayed() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    request = _request(idempotency_key="advisor-memo-corrupted")
    record_id = build_workflow_pack_execution_idempotency_record_id(
        caller_app=request.task_request.caller.caller_app,
        tenant_id=request.task_request.caller.tenant_id,
        idempotency_key="advisor-memo-corrupted",
    )
    repository.reserve(
        WorkflowPackExecutionIdempotencyRecord(
            record_id=record_id,
            caller_app=request.task_request.caller.caller_app,
            tenant_scope=request.task_request.caller.tenant_id or "__NO_TENANT__",
            idempotency_key="advisor-memo-corrupted",
            request_fingerprint=fingerprint_workflow_pack_execution_request(request),
            state=WorkflowPackExecutionIdempotencyState.IN_PROGRESS,
            owner_token="owner-corrupted",
            response_payload=None,
            response_checksum_sha256=None,
            failure_code=None,
            created_at="2026-08-28T01:00:00Z",
            updated_at="2026-08-28T01:00:00Z",
        )
    )
    repository.complete(
        record_id=record_id,
        owner_token="owner-corrupted",
        response_payload={"tampered": True},
        response_checksum_sha256="0" * 64,
        updated_at="2026-08-28T01:01:00Z",
    )

    with pytest.raises(HTTPException) as caught:
        execute_workflow_pack_idempotently(
            request,
            execute=execute_workflow_pack,
            repository=repository,
        )

    assert caught.value.status_code == 409
    assert "workflow_pack_execution_idempotency_result_integrity_mismatch" in str(
        caught.value.detail
    )


def test_preflight_http_failure_releases_key_for_corrected_retry() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    request = _request(idempotency_key="advisor-memo-preflight")
    attempts = 0

    def preflight_then_execute(
        value: WorkflowPackExecutionRequest,
    ) -> WorkflowPackExecutionResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPException(status_code=403, detail="execution is not eligible")
        return execute_workflow_pack(value)

    with pytest.raises(HTTPException) as caught:
        execute_workflow_pack_idempotently(
            request,
            execute=preflight_then_execute,
            repository=repository,
            owner_token="preflight-owner",
        )

    retried = execute_workflow_pack_idempotently(
        request,
        execute=preflight_then_execute,
        repository=repository,
        owner_token="corrected-owner",
    )

    assert caught.value.status_code == 403
    assert attempts == 2
    assert retried.idempotency is not None
    assert retried.idempotency.status is WorkflowPackExecutionIdempotencyStatus.CREATED


def test_omitted_key_preserves_non_idempotent_execution_compatibility() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    request = _request()

    first = execute_workflow_pack_idempotently(
        request,
        execute=execute_workflow_pack,
        repository=repository,
    )
    second = execute_workflow_pack_idempotently(
        request,
        execute=execute_workflow_pack,
        repository=repository,
    )

    assert first.idempotency is None
    assert second.idempotency is None
    assert first.workflow_pack_run.run_id != second.workflow_pack_run.run_id


def test_blank_key_is_rejected_before_execution() -> None:
    with pytest.raises(HTTPException) as caught:
        execute_workflow_pack_idempotently(
            _request(idempotency_key="   "),
            execute=execute_workflow_pack,
            repository=InMemoryWorkflowPackExecutionIdempotencyRepository(),
        )

    assert caught.value.status_code == 422
    assert "workflow_pack_execution_idempotency_key_invalid" in str(caught.value.detail)


def _request(
    *,
    idempotency_key: str | None = None,
    correlation_id: str = "corr-sync-idempotency",
) -> WorkflowPackExecutionRequest:
    payload = advisor_brief_workflow_pack_execution_request_json(correlation_id=correlation_id)
    payload["idempotency_key"] = idempotency_key
    return WorkflowPackExecutionRequest.model_validate(payload)
