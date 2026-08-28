from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.workflow_packs import (
    WorkflowPackExecutionIdempotencyDescriptor,
    WorkflowPackExecutionIdempotencyStatus,
    WorkflowPackExecutionRequest,
    WorkflowPackExecutionResponse,
)
from app.workflow_pack_execution_idempotency.repository import (
    WorkflowPackExecutionIdempotencyConflictError,
    WorkflowPackExecutionIdempotencyRecord,
    WorkflowPackExecutionIdempotencyRepository,
    WorkflowPackExecutionIdempotencyState,
)
from app.workflow_pack_execution_idempotency.store import (
    get_workflow_pack_execution_idempotency_store,
)

_NO_TENANT_SCOPE = "__NO_TENANT__"
_SYNC_EXECUTION_OPERATION = "workflow-pack-execute-sync"
WorkflowPackExecutor = Callable[[WorkflowPackExecutionRequest], WorkflowPackExecutionResponse]


def execute_workflow_pack_idempotently(
    request: WorkflowPackExecutionRequest,
    *,
    execute: WorkflowPackExecutor,
    repository: WorkflowPackExecutionIdempotencyRepository | None = None,
    owner_token: str | None = None,
    now: Callable[[], str] | None = None,
) -> WorkflowPackExecutionResponse:
    idempotency_key = _normalize_idempotency_key(request.idempotency_key)
    if idempotency_key is None:
        return execute(request)

    timestamp = (now or _utcnow)()
    request_fingerprint = fingerprint_workflow_pack_execution_request(request)
    record_id = build_workflow_pack_execution_idempotency_record_id(
        caller_app=request.task_request.caller.caller_app,
        tenant_id=request.task_request.caller.tenant_id,
        idempotency_key=idempotency_key,
    )
    execution_owner_token = owner_token or uuid4().hex
    store = repository or get_workflow_pack_execution_idempotency_store()
    proposed = WorkflowPackExecutionIdempotencyRecord(
        record_id=record_id,
        caller_app=request.task_request.caller.caller_app,
        tenant_scope=request.task_request.caller.tenant_id or _NO_TENANT_SCOPE,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        state=WorkflowPackExecutionIdempotencyState.IN_PROGRESS,
        owner_token=execution_owner_token,
        response_payload=None,
        failure_code=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    try:
        reservation = store.reserve(proposed)
    except WorkflowPackExecutionIdempotencyConflictError as exc:
        raise _conflict(
            "workflow_pack_execution_idempotency_conflict",
            "The idempotency key was already used with different workflow-pack input.",
        ) from exc

    if not reservation.acquired:
        return _resolve_existing_reservation(reservation.record)

    try:
        response = execute(request)
        created_response = _with_idempotency_status(
            response=response,
            status_value=WorkflowPackExecutionIdempotencyStatus.CREATED,
            record_id=record_id,
            request_fingerprint=request_fingerprint,
        )
        store.complete(
            record_id=record_id,
            owner_token=execution_owner_token,
            response_payload=created_response.model_dump(mode="json"),
            updated_at=(now or _utcnow)(),
        )
        return created_response
    except HTTPException:
        store.release(record_id=record_id, owner_token=execution_owner_token)
        raise
    except Exception:
        _mark_indeterminate_without_masking(
            repository=store,
            record_id=record_id,
            owner_token=execution_owner_token,
            now=now or _utcnow,
        )
        raise


def fingerprint_workflow_pack_execution_request(request: WorkflowPackExecutionRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"idempotency_key"})
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def build_workflow_pack_execution_idempotency_record_id(
    *, caller_app: str, tenant_id: str | None, idempotency_key: str
) -> str:
    scope = {
        "operation": _SYNC_EXECUTION_OPERATION,
        "caller_app": caller_app,
        "tenant_scope": tenant_id or _NO_TENANT_SCOPE,
        "idempotency_key": idempotency_key,
    }
    return "wpe_sync_" + hashlib.sha256(_canonical_json(scope)).hexdigest()[:32]


def _resolve_existing_reservation(
    record: WorkflowPackExecutionIdempotencyRecord,
) -> WorkflowPackExecutionResponse:
    if record.state is WorkflowPackExecutionIdempotencyState.COMPLETED:
        if record.response_payload is None:
            raise _conflict(
                "workflow_pack_execution_idempotency_result_missing",
                "The completed idempotent execution is missing its retained response.",
            )
        response = WorkflowPackExecutionResponse.model_validate(record.response_payload)
        return _with_idempotency_status(
            response=response,
            status_value=WorkflowPackExecutionIdempotencyStatus.REPLAYED,
            record_id=record.record_id,
            request_fingerprint=record.request_fingerprint,
        )
    if record.state is WorkflowPackExecutionIdempotencyState.INDETERMINATE:
        raise _conflict(
            "workflow_pack_execution_idempotency_outcome_indeterminate",
            "The original execution did not retain a completed response; automated replay is blocked to avoid duplicate AI execution.",
        )
    raise _conflict(
        "workflow_pack_execution_idempotency_in_progress",
        "The original workflow-pack execution is still in progress; no duplicate AI execution was started.",
    )


def _with_idempotency_status(
    *,
    response: WorkflowPackExecutionResponse,
    status_value: WorkflowPackExecutionIdempotencyStatus,
    record_id: str,
    request_fingerprint: str,
) -> WorkflowPackExecutionResponse:
    return response.model_copy(
        update={
            "idempotency": WorkflowPackExecutionIdempotencyDescriptor(
                status=status_value,
                record_id=record_id,
                request_fingerprint=request_fingerprint,
            )
        }
    )


def _mark_indeterminate_without_masking(
    *,
    repository: WorkflowPackExecutionIdempotencyRepository,
    record_id: str,
    owner_token: str,
    now: Callable[[], str],
) -> None:
    try:
        repository.mark_indeterminate(
            record_id=record_id,
            owner_token=owner_token,
            failure_code="execution_result_not_persisted",
            updated_at=now(),
        )
    except Exception:
        return


def _normalize_idempotency_key(idempotency_key: str | None) -> str | None:
    if idempotency_key is None:
        return None
    normalized = idempotency_key.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "workflow_pack_execution_idempotency_key_invalid: "
                "Idempotency key must contain a non-whitespace character."
            ),
        )
    return normalized


def _conflict(reason_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"{reason_code}: {message}",
    )


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
