from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.contracts.workflow_run_attestation import WorkflowRunAttestationKeyDiscoveryResponse
from app.providers.configured_workflow_run_attestation_keys import (
    ConfiguredWorkflowRunAttestationKeys,
)
from app.services.workflow_run_attestation_key_discovery import (
    build_workflow_run_attestation_key_discovery,
)


router = APIRouter(tags=["platform"])


@router.get(
    "/.well-known/lotus-ai-workflow-attestation-keys",
    response_model=WorkflowRunAttestationKeyDiscoveryResponse,
    operation_id="getWorkflowRunAttestationKeys",
    summary="Get workflow-run attestation verification keys",
    description=(
        "Returns active and historical public verification keys for signed lotus-ai workflow-run "
        "attestations. Private signing material is never exposed."
    ),
    responses={
        200: {"description": "Workflow-run attestation verification keys returned."},
        503: {"description": "Workflow-run attestation signing keys are not validly configured."},
    },
)
def get_workflow_run_attestation_keys() -> WorkflowRunAttestationKeyDiscoveryResponse:
    try:
        return build_workflow_run_attestation_key_discovery(
            key_source=ConfiguredWorkflowRunAttestationKeys(settings=settings)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEYS_UNAVAILABLE",
                "detail": f"Workflow-run attestation keys are unavailable: {exc}",
            },
        ) from exc
