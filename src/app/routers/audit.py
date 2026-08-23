from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.contracts.audit_access import (
    AuditAccessOperation,
    AuditAccessOutcome,
)
from app.contracts.audit import AuditRecordCatalogResponse, AuditRecordResponse
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.audit_read_authorization import (
    record_all_tenant_audit_access,
    resolve_audit_read_scope,
)
from app.services.audit_store import get_audit_store

router = APIRouter(prefix="/ai/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditRecordCatalogResponse,
    operation_id="listAuditRecords",
    summary="List lotus-ai audit records",
    description=(
        "Returns a tenant-scoped bounded catalog of lotus-ai audit records using optional caller "
        "and task filters. Tenant scope is derived from authenticated caller policy."
    ),
    responses={
        200: {"description": "Audit catalog returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_audit_records(
    authenticated_caller: AuthenticatedCallerDependency,
    caller_app: str | None = Query(
        default=None,
        description="Optional caller application filter for the audit catalog.",
    ),
    task_id: str | None = Query(
        default=None,
        description="Optional task identifier filter for the audit catalog.",
    ),
    category: str | None = Query(
        default=None,
        description="Optional task category filter for the audit catalog.",
    ),
    output_label: str | None = Query(
        default=None,
        description="Optional output label filter for the audit catalog.",
    ),
    requested_by: str | None = Query(
        default=None,
        description="Optional requester identity filter for the audit catalog.",
    ),
    tenant_id: str | None = Query(default=None, include_in_schema=False),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of audit records to return.",
    ),
) -> AuditRecordCatalogResponse:
    if tenant_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tenant scope is derived from authenticated caller policy.",
        )
    scope = resolve_audit_read_scope(authenticated_caller)
    records = get_audit_store().list(
        caller_app=caller_app,
        task_id=task_id,
        category=category,
        output_label=output_label,
        requested_by=requested_by,
        scope=scope,
        limit=limit,
    )
    record_all_tenant_audit_access(
        caller=authenticated_caller,
        scope=scope,
        operation=AuditAccessOperation.LIST_RECORDS,
        outcome=AuditAccessOutcome.SUCCEEDED,
        returned_record_count=len(records),
    )
    filters_applied: dict[str, str | int] = {
        "limit": limit,
        "tenant_scope": scope.mode.value,
    }
    if caller_app is not None:
        filters_applied["caller_app"] = caller_app
    if task_id is not None:
        filters_applied["task_id"] = task_id
    if category is not None:
        filters_applied["category"] = category
    if output_label is not None:
        filters_applied["output_label"] = output_label
    if requested_by is not None:
        filters_applied["requested_by"] = requested_by
    return AuditRecordCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        record_count=len(records),
        filters_applied=filters_applied,
        records=records,
    )


@router.get(
    "/{request_id}",
    response_model=AuditRecordResponse,
    operation_id="getAuditRecord",
    summary="Get lotus-ai audit record",
    description=(
        "Returns the stored audit record for a prior lotus-ai task execution request. "
        "During foundation phase, records are stored in an in-memory audit store."
    ),
    responses={
        200: {"description": "Audit record returned successfully."},
        404: {"description": "Audit record not found for the given request id."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_audit_record(
    request_id: str,
    authenticated_caller: AuthenticatedCallerDependency,
) -> AuditRecordResponse:
    scope = resolve_audit_read_scope(authenticated_caller)
    record = get_audit_store().get(request_id, scope=scope)
    if record is None:
        record_all_tenant_audit_access(
            caller=authenticated_caller,
            scope=scope,
            operation=AuditAccessOperation.GET_RECORD,
            outcome=AuditAccessOutcome.NOT_FOUND,
            returned_record_count=0,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No lotus-ai audit record found for the requested identifier.",
        )
    record_all_tenant_audit_access(
        caller=authenticated_caller,
        scope=scope,
        operation=AuditAccessOperation.GET_RECORD,
        outcome=AuditAccessOutcome.SUCCEEDED,
        returned_record_count=1,
    )
    return record
