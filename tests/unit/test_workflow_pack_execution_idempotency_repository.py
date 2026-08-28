from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.workflow_pack_execution_idempotency.memory_repository import (
    InMemoryWorkflowPackExecutionIdempotencyRepository,
)
from app.workflow_pack_execution_idempotency.repository import (
    WorkflowPackExecutionIdempotencyConflictError,
    WorkflowPackExecutionIdempotencyRecord,
    WorkflowPackExecutionIdempotencyState,
)
from app.workflow_pack_execution_idempotency.sqlalchemy_repository import (
    SqlAlchemyWorkflowPackExecutionIdempotencyRepository,
)
from app.workflow_pack_execution_idempotency.service import checksum_response_payload
from tests.support.migration_runner import upgrade_database_to_head


def test_memory_repository_reserves_one_owner_and_replays_completed_record() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    record = _record()

    first = repository.reserve(record)
    duplicate = repository.reserve(_record(owner_token="owner-b"))
    response_payload: dict[str, object] = {"workflow_pack_run": {"run_id": "run-001"}}
    completed = repository.complete(
        record_id=record.record_id,
        owner_token=record.owner_token,
        response_payload=response_payload,
        response_checksum_sha256=checksum_response_payload(response_payload),
        updated_at="2026-08-28T01:01:00Z",
    )
    replay = repository.reserve(_record(owner_token="owner-c"))

    assert first.acquired is True
    assert duplicate.acquired is False
    assert duplicate.record.owner_token == "owner-a"
    assert completed.state is WorkflowPackExecutionIdempotencyState.COMPLETED
    assert replay.acquired is False
    assert replay.record == completed


def test_memory_repository_rejects_same_key_with_different_fingerprint() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    repository.reserve(_record())

    with pytest.raises(WorkflowPackExecutionIdempotencyConflictError):
        repository.reserve(_record(request_fingerprint="b" * 64))


def test_memory_repository_allows_only_one_concurrent_reservation_owner() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()

    def reserve(owner_number: int) -> bool:
        return repository.reserve(_record(owner_token=f"owner-{owner_number}")).acquired

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(reserve, range(8)))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 7


def test_sql_repository_survives_restart_and_replays_completed_response(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-execution-idempotency.sqlite3'}"
    upgrade_database_to_head(database_url)
    first = SqlAlchemyWorkflowPackExecutionIdempotencyRepository(database_url)
    record = _record()
    assert first.reserve(record).acquired is True
    response_payload: dict[str, object] = {"workflow_pack_run": {"run_id": "run-001"}}
    first.complete(
        record_id=record.record_id,
        owner_token=record.owner_token,
        response_payload=response_payload,
        response_checksum_sha256=checksum_response_payload(response_payload),
        updated_at="2026-08-28T01:01:00Z",
    )
    first.close()

    restarted = SqlAlchemyWorkflowPackExecutionIdempotencyRepository(database_url)
    replay = restarted.reserve(_record(owner_token="owner-after-restart"))
    restarted.close()

    assert replay.acquired is False
    assert replay.record.state is WorkflowPackExecutionIdempotencyState.COMPLETED
    assert replay.record.response_payload == {"workflow_pack_run": {"run_id": "run-001"}}


def test_sql_repository_serializes_concurrent_same_key_reservations(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-execution-concurrency.sqlite3'}"
    upgrade_database_to_head(database_url)

    def reserve(owner_number: int) -> bool:
        repository = SqlAlchemyWorkflowPackExecutionIdempotencyRepository(database_url)
        try:
            return repository.reserve(_record(owner_token=f"owner-{owner_number}")).acquired
        finally:
            repository.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(reserve, range(8)))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 7


def test_repository_marks_uncertain_post_provider_failures_indeterminate() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    record = _record()
    repository.reserve(record)

    indeterminate = repository.mark_indeterminate(
        record_id=record.record_id,
        owner_token=record.owner_token,
        failure_code="execution_result_not_persisted",
        updated_at="2026-08-28T01:01:00Z",
    )

    assert indeterminate.state is WorkflowPackExecutionIdempotencyState.INDETERMINATE
    assert indeterminate.response_payload is None
    assert indeterminate.failure_code == "execution_result_not_persisted"


def test_repository_releases_only_the_active_reservation_owner() -> None:
    repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    record = _record()
    repository.reserve(record)

    repository.release(record_id=record.record_id, owner_token=record.owner_token)

    assert repository.get(record_id=record.record_id) is None
    assert repository.reserve(_record(owner_token="replacement-owner")).acquired is True


def _record(**overrides: str) -> WorkflowPackExecutionIdempotencyRecord:
    values = {
        "record_id": "wpe_sync_" + "a" * 32,
        "caller_app": "lotus-advise",
        "tenant_scope": "SG_PRIVATE_BANK",
        "idempotency_key": "memo-request-001",
        "request_fingerprint": "a" * 64,
        "owner_token": "owner-a",
    }
    values.update(overrides)
    return WorkflowPackExecutionIdempotencyRecord(
        **values,
        state=WorkflowPackExecutionIdempotencyState.IN_PROGRESS,
        response_payload=None,
        response_checksum_sha256=None,
        failure_code=None,
        created_at="2026-08-28T01:00:00Z",
        updated_at="2026-08-28T01:00:00Z",
    )
