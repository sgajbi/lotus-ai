from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.contracts.workflow_run_attestation import WorkflowRunAttestationKeyDiscoveryResponse
from app.providers.configured_workflow_run_attestation_keys import (
    ConfiguredWorkflowRunAttestationKeys,
)
from app.services.workflow_run_attestation_key_discovery import (
    build_workflow_run_attestation_key_discovery,
)
from app.services.workflow_run_attestation_issuance import (
    WorkflowRunAttestationNotIssuableError,
    WorkflowRunAttestationRunNotFoundError,
    issue_workflow_run_attestation,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.contracts.workflow_run_attestation import WorkflowRunAttestationEnvelope


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


@router.get(
    "/platform/workflow-packs/runs/{run_id}/attestation",
    response_model=WorkflowRunAttestationEnvelope,
    operation_id="getWorkflowPackRunAttestation",
    summary="Get a signed workflow-pack run attestation",
    description=(
        "Issues a short-lived signed attestation only for a completed, supportable, non-stub "
        "workflow-pack run with an approved model-risk decision."
    ),
    responses={
        200: {"description": "Signed workflow-pack run attestation returned."},
        404: {"description": "Workflow-pack run not found."},
        409: {"description": "Workflow-pack run is not eligible for attestation."},
        503: {"description": "Attestation signing or run storage is unavailable."},
    },
)
def get_workflow_pack_run_attestation(run_id: str) -> WorkflowRunAttestationEnvelope:
    try:
        configured_keys = ConfiguredWorkflowRunAttestationKeys(settings=settings)
        return issue_workflow_run_attestation(
            run_id=run_id,
            run_repository=get_workflow_pack_run_store(),
            signer=configured_keys,
            ttl_seconds=settings.workflow_run_attestation_ttl_seconds,
        )
    except WorkflowRunAttestationRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkflowRunAttestationNotIssuableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "LOTUS_AI_WORKFLOW_RUN_ATTESTATION_NOT_ISSUABLE",
                "detail": str(exc),
                "metadata": {"reason_code": exc.reason_code, "run_id": run_id},
            },
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LOTUS_AI_WORKFLOW_RUN_ATTESTATION_UNAVAILABLE",
                "detail": f"Workflow-run attestation is unavailable: {exc}",
            },
        ) from exc
