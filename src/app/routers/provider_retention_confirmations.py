from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.provider_retention_confirmations.contracts import (
    ProviderRetentionConfirmationEnvelope,
    ProviderRetentionConfirmationRequest,
)
from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationConflictError,
)
from app.provider_retention_confirmations.service import (
    ProviderRetentionConfirmationNotFoundError,
    ProviderRetentionConfirmationNotIssuableError,
    issue_provider_retention_confirmation,
)
from app.provider_retention_confirmations.store import (
    get_provider_retention_confirmation_store,
)
from app.providers.configured_workflow_run_attestation_keys import (
    ConfiguredWorkflowRunAttestationKeys,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store

router = APIRouter(tags=["platform"])


@router.post(
    "/platform/provider-operations/workflow-runs/{run_id}/retention-confirmations",
    response_model=ProviderRetentionConfirmationEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="issueProviderRetentionConfirmation",
    summary="Issue a signed provider retention or deletion confirmation",
    description=(
        "Allows only AI provider operations to record and sign source-safe provider retention, "
        "no-storage, deletion, or failure posture for a completed live Idea explanation run. "
        "Provider/model/tenant "
        "identity comes from the persisted run; prompts, outputs, client identifiers, and "
        "provider secrets are forbidden."
    ),
    responses={
        201: {"description": "Signed provider retention confirmation issued or replayed."},
        404: {"description": "Workflow run not found."},
        409: {"description": "Run is ineligible or the idempotency key conflicts."},
        422: {"description": "Request or required headers are invalid."},
        503: {"description": "Signing or confirmation persistence is unavailable."},
    },
)
def issue_provider_retention_confirmation_route(
    run_id: str,
    request: ProviderRetentionConfirmationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    caller_app: Annotated[str, Header(alias="X-Caller-App", min_length=1)],
    tenant_id: Annotated[str, Header(alias="X-Tenant-Id", min_length=1)],
) -> ProviderRetentionConfirmationEnvelope:
    try:
        return issue_provider_retention_confirmation(
            run_id=run_id,
            request=request,
            idempotency_key=idempotency_key.strip(),
            caller_app=caller_app.strip(),
            tenant_id=tenant_id.strip(),
            run_repository=get_workflow_pack_run_store(),
            confirmation_repository=get_provider_retention_confirmation_store(),
            signer=ConfiguredWorkflowRunAttestationKeys(settings=settings),
            ttl_seconds=settings.workflow_run_attestation_ttl_seconds,
        )
    except ProviderRetentionConfirmationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (
        ProviderRetentionConfirmationConflictError,
        ProviderRetentionConfirmationNotIssuableError,
    ) as exc:
        reason_code = getattr(exc, "reason_code", "idempotency_conflict")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "LOTUS_AI_PROVIDER_RETENTION_CONFIRMATION_NOT_ISSUABLE",
                "detail": str(exc),
                "metadata": {"reason_code": reason_code, "run_id": run_id},
            },
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LOTUS_AI_PROVIDER_RETENTION_CONFIRMATION_UNAVAILABLE",
                "detail": f"Provider retention confirmation is unavailable: {exc}",
            },
        ) from exc
