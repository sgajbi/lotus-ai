from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.contracts.audit import AuditRecordResponse
from app.services.audit_store import get_audit_store

router = APIRouter(prefix="/ai/audit", tags=["audit"])


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
async def get_audit_record(request_id: str) -> AuditRecordResponse:
    record = get_audit_store().get(request_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No lotus-ai audit record found for request_id: {request_id}",
        )
    return record
