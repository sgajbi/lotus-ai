from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.contracts.workflow_packs import (
    WorkflowPackControlActionRequest,
    WorkflowPackControlActionResponse,
    WorkflowPackControlHistoryResponse,
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackEligibilityEvaluationResponse,
    WorkflowPackAsyncExecutionSubmissionResponse,
    WorkflowPackExecutionRequest,
    WorkflowPackExecutionResponse,
    WorkflowPackRegistrationDetailResponse,
    WorkflowPackRegistryCatalogResponse,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
    WorkflowPackRunConsumerViewResponse,
    WorkflowPackRunDetailResponse,
    WorkflowPackRunOperatorProfileResponse,
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionResponse,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSourceEventResponse,
    WorkflowPackSourceEventCatalogResponse,
    WorkflowPackRunSupportabilityStatus,
)
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventCatalogResponse,
    WorkflowPackQueueEventDetailResponse,
    WorkflowPackQueuePolicyCatalogResponse,
    WorkflowPackQueuePolicyDetailResponse,
    WorkflowPackQueueRecoveryDecisionResponse,
    WorkflowPackQueueReplayDecisionRequest,
    WorkflowPackQueueRetryDecisionRequest,
    WorkflowPackQueueStatusDetailResponse,
    WorkflowPackQueueStatusResponse,
)
from app.contracts.workflow_pack_queue_recovery import (
    WorkflowPackQueueRecoveryExecutionResponse,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCatalogResponse,
    WorkflowPackTaskFlowCheckpointCatalogResponse,
    WorkflowPackTaskFlowDetailResponse,
    WorkflowPackTaskFlowStatus,
)
from app.services.workflow_pack_run_consumer_view import build_workflow_pack_run_consumer_view
from app.services.workflow_pack_run_operator_profile import build_workflow_pack_run_operator_profile
from app.services.workflow_pack_control import (
    apply_workflow_pack_control_action,
    build_workflow_pack_control_history,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
from app.services.workflow_pack_execution import execute_workflow_pack
from app.services.workflow_pack_async_execution import submit_workflow_pack_execution_async
from app.services.workflow_pack_run_ledger import (
    WorkflowPackRunStoreUnavailableError,
    build_workflow_pack_run_catalog,
    build_workflow_pack_run_detail,
)
from app.services.workflow_pack_run_review import apply_workflow_pack_run_review_action
from app.services.workflow_pack_source_events import (
    build_workflow_pack_run_source_events,
    build_workflow_pack_source_event_catalog,
)
from app.services.workflow_pack_task_flow_service import (
    WorkflowPackTaskFlowNotFoundError,
    WorkflowPackTaskFlowStoreNotReadyError,
    build_workflow_pack_task_flow_catalog,
    build_workflow_pack_task_flow_checkpoint_catalog,
    build_workflow_pack_task_flow_detail,
)
from app.services.workflow_pack_registry import (
    WorkflowPackRegistryUnavailableError,
    build_workflow_pack_registration_detail,
    build_workflow_pack_registry_catalog,
)
from app.services.workflow_pack_queue_policy_catalog import (
    build_workflow_pack_queue_policy_catalog,
    build_workflow_pack_queue_policy_detail,
    build_workflow_pack_queue_status,
    build_workflow_pack_queue_status_detail,
)
from app.services.workflow_pack_queue_events import (
    WorkflowPackQueueEventStoreNotReadyError,
    build_workflow_pack_queue_event_catalog,
    build_workflow_pack_queue_event_detail,
)
from app.services.workflow_pack_queue_recovery import (
    record_workflow_pack_queue_replay_decision,
    record_workflow_pack_queue_retry_decision,
)
from app.services.workflow_pack_queue_recovery_execution import (
    execute_workflow_pack_queue_replay,
    execute_workflow_pack_queue_retry,
)

router = APIRouter(tags=["platform"])


@router.get(
    "/platform/workflow-packs/registry",
    response_model=WorkflowPackRegistryCatalogResponse,
    operation_id="getWorkflowPackRegistryCatalog",
    summary="Get lotus-ai workflow-pack registry catalog",
    description=(
        "Returns the current workflow-pack registry and validation posture exposed by lotus-ai. "
        "This registry is the control-plane record for known workflow-pack versions, not the editable home of workflow logic."
    ),
    responses={
        200: {"description": "Workflow-pack registry catalog returned successfully."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_registry_catalog() -> WorkflowPackRegistryCatalogResponse:
    try:
        return build_workflow_pack_registry_catalog()
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/registry/{pack_id}/{version}",
    response_model=WorkflowPackRegistrationDetailResponse,
    operation_id="getWorkflowPackRegistrationDetail",
    summary="Get lotus-ai workflow-pack registration detail",
    description=(
        "Returns one workflow-pack registration record, including bounded ownership, scope, and registration-validation posture."
    ),
    responses={
        200: {"description": "Workflow-pack registration detail returned successfully."},
        404: {"description": "Workflow-pack registration not found."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_registration_detail(
    pack_id: str,
    version: str,
) -> WorkflowPackRegistrationDetailResponse:
    try:
        return build_workflow_pack_registration_detail(pack_id=pack_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/queue-policies",
    response_model=WorkflowPackQueuePolicyCatalogResponse,
    operation_id="getWorkflowPackQueuePolicyCatalog",
    summary="Get lotus-ai workflow-pack queue policy catalog",
    description=(
        "Returns declared per-pack queue policies for executable workflow-pack versions. "
        "This is source policy posture, not a mutation or worker-control surface."
    ),
    responses={
        200: {"description": "Workflow-pack queue policy catalog returned successfully."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_queue_policy_catalog_route() -> WorkflowPackQueuePolicyCatalogResponse:
    try:
        return build_workflow_pack_queue_policy_catalog()
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/queue-policies/{pack_id}/{version}",
    response_model=WorkflowPackQueuePolicyDetailResponse,
    operation_id="getWorkflowPackQueuePolicyDetail",
    summary="Get lotus-ai workflow-pack queue policy detail",
    description=(
        "Returns one declared workflow-pack queue policy while preserving the separation between "
        "queue policy, queue admission, run lifecycle, and task-flow lifecycle."
    ),
    responses={
        200: {"description": "Workflow-pack queue policy detail returned successfully."},
        404: {"description": "Workflow-pack queue policy not found."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_queue_policy_detail_route(
    pack_id: str,
    version: str,
) -> WorkflowPackQueuePolicyDetailResponse:
    try:
        return build_workflow_pack_queue_policy_detail(pack_id=pack_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/queue-status",
    response_model=WorkflowPackQueueStatusResponse,
    operation_id="getWorkflowPackQueueStatus",
    summary="Get lotus-ai workflow-pack queue status",
    description=(
        "Returns bounded current workflow-pack queue admission posture without exposing raw worker "
        "or lock internals."
    ),
    responses={
        200: {"description": "Workflow-pack queue status returned successfully."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_queue_status_route() -> WorkflowPackQueueStatusResponse:
    try:
        return build_workflow_pack_queue_status()
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/queue-status/{queue_item_id}",
    response_model=WorkflowPackQueueStatusDetailResponse,
    operation_id="getWorkflowPackQueueStatusDetail",
    summary="Get lotus-ai workflow-pack queue status detail",
    description="Returns one bounded active workflow-pack queue admission item.",
    responses={
        200: {"description": "Workflow-pack queue status detail returned successfully."},
        404: {"description": "Workflow-pack queue item not found."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_queue_status_detail_route(
    queue_item_id: str,
) -> WorkflowPackQueueStatusDetailResponse:
    try:
        return build_workflow_pack_queue_status_detail(queue_item_id=queue_item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/queue-events",
    response_model=WorkflowPackQueueEventCatalogResponse,
    operation_id="getWorkflowPackQueueEventCatalog",
    summary="Get lotus-ai workflow-pack queue event catalog",
    description=(
        "Returns durable queue admission, rejection, and release evidence without exposing raw "
        "worker internals or replacing run-ledger lifecycle posture."
    ),
    responses={
        200: {"description": "Workflow-pack queue event catalog returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        503: {"description": "Workflow-pack queue event store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_queue_event_catalog_route(
    queue_item_id: str | None = Query(
        default=None,
        description="Optional queue item identifier filter.",
    ),
    workflow_pack_id: str | None = Query(
        default=None,
        description="Optional workflow-pack identifier filter.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of queue events to return after filtering.",
    ),
) -> WorkflowPackQueueEventCatalogResponse:
    try:
        return build_workflow_pack_queue_event_catalog(
            queue_item_id=queue_item_id,
            workflow_pack_id=workflow_pack_id,
            limit=limit,
        )
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/queue-events/{queue_item_id}",
    response_model=WorkflowPackQueueEventDetailResponse,
    operation_id="getWorkflowPackQueueEventDetail",
    summary="Get lotus-ai workflow-pack queue event detail",
    description=("Returns the bounded event history for one workflow-pack queue admission item."),
    responses={
        200: {"description": "Workflow-pack queue event detail returned successfully."},
        404: {"description": "Unknown workflow-pack queue item history."},
        503: {"description": "Workflow-pack queue event store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_queue_event_detail_route(
    queue_item_id: str,
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of events to return for this queue item.",
    ),
) -> WorkflowPackQueueEventDetailResponse:
    try:
        return build_workflow_pack_queue_event_detail(
            queue_item_id=queue_item_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/queue-events/{queue_item_id}/retry-decisions",
    response_model=WorkflowPackQueueRecoveryDecisionResponse,
    operation_id="recordWorkflowPackQueueRetryDecision",
    summary="Record lotus-ai workflow-pack queue retry decision",
    description=(
        "Records bounded retry decision evidence for a terminal workflow-pack queue item. "
        "This does not execute the workflow body again."
    ),
    responses={
        200: {"description": "Workflow-pack queue retry decision recorded successfully."},
        404: {"description": "Unknown workflow-pack queue item history."},
        409: {"description": "Queue item is not eligible for recovery decision recording."},
        422: {"description": "Invalid retry decision request supplied."},
        503: {"description": "Workflow-pack queue event store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def record_workflow_pack_queue_retry_decision_route(
    queue_item_id: str,
    request: WorkflowPackQueueRetryDecisionRequest,
) -> WorkflowPackQueueRecoveryDecisionResponse:
    try:
        event = record_workflow_pack_queue_retry_decision(
            queue_item_id=queue_item_id,
            failure_code=request.failure_code,
            requested_by=request.requested_by,
            reason=request.reason,
            evidence_ref=request.evidence_ref,
        )
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WorkflowPackQueueRecoveryDecisionResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        event=event,
        status_summary=[
            "Workflow-pack queue retry decision evidence was recorded durably.",
            "This response does not claim that workflow-pack execution was retried.",
        ],
    )


@router.post(
    "/platform/workflow-packs/queue-events/{queue_item_id}/retry-executions",
    response_model=WorkflowPackQueueRecoveryExecutionResponse,
    operation_id="executeWorkflowPackQueueRetry",
    summary="Execute lotus-ai workflow-pack queue retry",
    description=(
        "Records bounded retry decision evidence for a terminal workflow-pack queue item, "
        "reconstructs the retained request snapshot, and executes the workflow pack through the "
        "normal governed execution path."
    ),
    responses={
        200: {"description": "Workflow-pack queue retry executed successfully."},
        404: {"description": "Unknown workflow-pack queue item history."},
        409: {"description": "Queue item is not eligible for retry execution."},
        422: {"description": "Invalid retry execution request supplied."},
        503: {"description": "Workflow-pack queue event store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def execute_workflow_pack_queue_retry_route(
    queue_item_id: str,
    request: WorkflowPackQueueRetryDecisionRequest,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    try:
        return execute_workflow_pack_queue_retry(
            queue_item_id=queue_item_id,
            failure_code=request.failure_code,
            requested_by=request.requested_by,
            reason=request.reason,
            evidence_ref=request.evidence_ref,
        )
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/queue-events/{queue_item_id}/replay-decisions",
    response_model=WorkflowPackQueueRecoveryDecisionResponse,
    operation_id="recordWorkflowPackQueueReplayDecision",
    summary="Record lotus-ai workflow-pack queue replay decision",
    description=(
        "Records bounded replay decision evidence for a terminal workflow-pack queue item. "
        "This does not execute the workflow body again."
    ),
    responses={
        200: {"description": "Workflow-pack queue replay decision recorded successfully."},
        404: {"description": "Unknown workflow-pack queue item history."},
        409: {"description": "Queue item is not eligible for recovery decision recording."},
        422: {"description": "Invalid replay decision request supplied."},
        503: {"description": "Workflow-pack queue event store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def record_workflow_pack_queue_replay_decision_route(
    queue_item_id: str,
    request: WorkflowPackQueueReplayDecisionRequest,
) -> WorkflowPackQueueRecoveryDecisionResponse:
    try:
        event = record_workflow_pack_queue_replay_decision(
            queue_item_id=queue_item_id,
            requested_by=request.requested_by,
            reason=request.reason,
            evidence_ref=request.evidence_ref,
        )
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WorkflowPackQueueRecoveryDecisionResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        event=event,
        status_summary=[
            "Workflow-pack queue replay decision evidence was recorded durably.",
            "This response does not claim that workflow-pack execution was replayed.",
        ],
    )


@router.post(
    "/platform/workflow-packs/queue-events/{queue_item_id}/replay-executions",
    response_model=WorkflowPackQueueRecoveryExecutionResponse,
    operation_id="executeWorkflowPackQueueReplay",
    summary="Execute lotus-ai workflow-pack queue replay",
    description=(
        "Records bounded replay decision evidence for a terminal workflow-pack queue item, "
        "reconstructs the retained request snapshot, and executes the workflow pack through the "
        "normal governed execution path."
    ),
    responses={
        200: {"description": "Workflow-pack queue replay executed successfully."},
        404: {"description": "Unknown workflow-pack queue item history."},
        409: {"description": "Queue item is not eligible for replay execution."},
        422: {"description": "Invalid replay execution request supplied."},
        503: {"description": "Workflow-pack queue event store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def execute_workflow_pack_queue_replay_route(
    queue_item_id: str,
    request: WorkflowPackQueueReplayDecisionRequest,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    try:
        return execute_workflow_pack_queue_replay(
            queue_item_id=queue_item_id,
            requested_by=request.requested_by,
            reason=request.reason,
            evidence_ref=request.evidence_ref,
        )
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/eligibility/evaluate",
    response_model=WorkflowPackEligibilityEvaluationResponse,
    operation_id="evaluateWorkflowPackEligibility",
    summary="Evaluate lotus-ai workflow-pack eligibility",
    description=(
        "Evaluates whether one workflow-pack version is currently eligible for execution under the declared caller, environment, and workflow-scope posture."
    ),
    responses={
        200: {"description": "Workflow-pack eligibility evaluated successfully."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def evaluate_workflow_pack_eligibility_route(
    request: WorkflowPackEligibilityEvaluationRequest,
) -> WorkflowPackEligibilityEvaluationResponse:
    try:
        return evaluate_workflow_pack_eligibility(request)
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/execute",
    response_model=WorkflowPackExecutionResponse,
    operation_id="executeWorkflowPack",
    summary="Execute a lotus-ai workflow pack through the explicit workflow-pack seam",
    description=(
        "Evaluates workflow-pack eligibility, runs the bounded lotus-ai task pipeline for the "
        "declared pack binding, and records an explicit workflow-pack run."
    ),
    responses={
        200: {"description": "Workflow-pack executed successfully."},
        403: {"description": "Workflow-pack execution is not currently allowed."},
        404: {"description": "Workflow-pack registration not found."},
        409: {"description": "Workflow-pack execution binding is not available for this request."},
        422: {"description": "Workflow-pack execution payload is invalid for the requested pack."},
        503: {"description": "Workflow-pack runtime dependency store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def execute_workflow_pack_route(
    request: WorkflowPackExecutionRequest,
) -> WorkflowPackExecutionResponse:
    try:
        return execute_workflow_pack(request)
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/execute-async",
    response_model=WorkflowPackAsyncExecutionSubmissionResponse,
    operation_id="submitWorkflowPackAsyncExecution",
    summary="Submit a lotus-ai workflow pack for durable async execution",
    description=(
        "Evaluates workflow-pack eligibility, validates the bounded execution request, records "
        "durable queue-event and request-snapshot evidence, and persists a workflow-pack async "
        "runtime job for dedicated worker execution."
    ),
    responses={
        200: {"description": "Workflow-pack async execution submitted successfully."},
        403: {"description": "Workflow-pack execution is not currently allowed."},
        404: {"description": "Workflow-pack registration not found."},
        409: {"description": "Workflow-pack async execution conflicts with queue policy."},
        422: {"description": "Workflow-pack execution payload is invalid."},
        429: {"description": "Workflow-pack async queue capacity is saturated."},
        503: {"description": "Workflow-pack runtime dependency store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def submit_workflow_pack_async_execution_route(
    request: WorkflowPackExecutionRequest,
) -> WorkflowPackAsyncExecutionSubmissionResponse:
    try:
        return submit_workflow_pack_execution_async(request)
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/control-history",
    response_model=WorkflowPackControlHistoryResponse,
    operation_id="getWorkflowPackControlHistory",
    summary="Get lotus-ai workflow-pack control history",
    description=(
        "Returns recent workflow-pack pause, resume, deprecate, and retire actions recorded by the workflow-pack control plane."
    ),
    responses={
        200: {"description": "Workflow-pack control history returned successfully."},
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_control_history_route(
    pack_id: str | None = None,
    version: str | None = None,
    limit: int = 20,
) -> WorkflowPackControlHistoryResponse:
    try:
        return build_workflow_pack_control_history(pack_id=pack_id, version=version, limit=limit)
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/runs",
    response_model=WorkflowPackRunCatalogResponse,
    operation_id="getWorkflowPackRunCatalog",
    summary="Get lotus-ai workflow-pack run catalog",
    description=(
        "Returns the current workflow-pack run-ledger catalog, including runtime-state and "
        "review-state posture for recorded workflow-pack executions."
    ),
    responses={
        200: {"description": "Workflow-pack run catalog returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_catalog_route(
    registration_ref: str | None = Query(
        default=None,
        description="Optional workflow-pack registration reference filter.",
    ),
    pack_id: str | None = Query(
        default=None,
        description="Optional workflow-pack identifier filter.",
    ),
    caller_app: str | None = Query(
        default=None,
        description="Optional caller-application filter for the run catalog.",
    ),
    tenant_id: str | None = Query(
        default=None,
        description="Optional tenant identifier filter for the run catalog.",
    ),
    workflow_surface: str | None = Query(
        default=None,
        description="Optional workflow-surface filter for the run catalog.",
    ),
    runtime_state: WorkflowPackRunRuntimeState | None = Query(
        default=None,
        description="Optional runtime-state filter for the run catalog.",
    ),
    review_state: WorkflowPackRunReviewState | None = Query(
        default=None,
        description="Optional review-state filter for the run catalog.",
    ),
    supportability_status: WorkflowPackRunSupportabilityStatus | None = Query(
        default=None,
        description="Optional supportability-status filter derived from the shared run posture seam.",
    ),
    workflow_authority_owner: str | None = Query(
        default=None,
        description="Optional workflow-authority owner filter for the run catalog.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of workflow-pack runs to return after filtering.",
    ),
) -> WorkflowPackRunCatalogResponse:
    try:
        return build_workflow_pack_run_catalog(
            registration_ref=registration_ref,
            pack_id=pack_id,
            caller_app=caller_app,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            runtime_state=runtime_state,
            review_state=review_state,
            supportability_status=supportability_status,
            workflow_authority_owner=workflow_authority_owner,
            limit=limit,
        )
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/source-events",
    response_model=WorkflowPackSourceEventCatalogResponse,
    operation_id="getWorkflowPackSourceEventCatalog",
    summary="Get lotus-ai workflow-pack source-event catalog",
    description=(
        "Returns AI-owned source events projected from workflow-pack run-ledger truth. The response "
        "omits raw prompts, raw generated output, and raw portfolio-memory payloads while preserving "
        "bounded lineage, review, artifact, and supportability posture for downstream portfolio-memory consumers."
    ),
    responses={
        200: {"description": "Workflow-pack source-event catalog returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_source_event_catalog_route(
    pack_id: str | None = Query(
        default=None,
        description="Optional workflow-pack identifier filter.",
    ),
    caller_app: str | None = Query(
        default=None,
        description="Optional caller-application filter.",
    ),
    tenant_id: str | None = Query(
        default=None,
        description="Optional tenant identifier filter.",
    ),
    workflow_surface: str | None = Query(
        default=None,
        description="Optional workflow-surface filter.",
    ),
    supportability_status: WorkflowPackRunSupportabilityStatus | None = Query(
        default=None,
        description="Optional supportability-status filter derived from workflow-pack run posture.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of AI source events to return after filtering.",
    ),
) -> WorkflowPackSourceEventCatalogResponse:
    try:
        return build_workflow_pack_source_event_catalog(
            pack_id=pack_id,
            caller_app=caller_app,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            supportability_status=supportability_status,
            limit=limit,
        )
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/task-flows",
    response_model=WorkflowPackTaskFlowCatalogResponse,
    operation_id="getWorkflowPackTaskFlowCatalog",
    summary="Get lotus-ai workflow-pack task-flow catalog",
    description=(
        "Returns recorded long-running workflow-pack task-flow posture. This is a read-only "
        "inspection surface; consequence-bearing workflow authority remains with the owning domain service."
    ),
    responses={
        200: {"description": "Workflow-pack task-flow catalog returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        503: {"description": "Workflow-pack task-flow store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_task_flow_catalog_route(
    workflow_pack_id: str | None = Query(
        default=None,
        description="Optional workflow-pack identifier filter.",
    ),
    caller: str | None = Query(
        default=None,
        description="Optional caller-application filter.",
    ),
    tenant_id: str | None = Query(
        default=None,
        description="Optional tenant identifier filter.",
    ),
    workflow_surface: str | None = Query(
        default=None,
        description="Optional workflow-surface filter.",
    ),
    flow_status: WorkflowPackTaskFlowStatus | None = Query(
        default=None,
        description="Optional task-flow lifecycle-state filter.",
    ),
    supportability_status: WorkflowPackRunSupportabilityStatus | None = Query(
        default=None,
        description="Optional supportability-status filter.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of task flows to return after filtering.",
    ),
) -> WorkflowPackTaskFlowCatalogResponse:
    try:
        return build_workflow_pack_task_flow_catalog(
            workflow_pack_id=workflow_pack_id,
            caller=caller,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            flow_status=flow_status,
            supportability_status=supportability_status,
            limit=limit,
        )
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/task-flows/{task_flow_id}",
    response_model=WorkflowPackTaskFlowDetailResponse,
    operation_id="getWorkflowPackTaskFlowDetail",
    summary="Get lotus-ai workflow-pack task-flow detail",
    description=(
        "Returns one task-flow descriptor and its checkpoint history while preserving the "
        "separation between task-flow posture, run state, review state, and domain handoff authority."
    ),
    responses={
        200: {"description": "Workflow-pack task-flow detail returned successfully."},
        404: {"description": "Unknown workflow-pack task-flow identifier."},
        503: {"description": "Workflow-pack task-flow store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_task_flow_detail_route(
    task_flow_id: str,
) -> WorkflowPackTaskFlowDetailResponse:
    try:
        return build_workflow_pack_task_flow_detail(task_flow_id)
    except WorkflowPackTaskFlowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/task-flows/{task_flow_id}/checkpoints",
    response_model=WorkflowPackTaskFlowCheckpointCatalogResponse,
    operation_id="getWorkflowPackTaskFlowCheckpointCatalog",
    summary="Get lotus-ai workflow-pack task-flow checkpoints",
    description=(
        "Returns recorded checkpoints for one task flow, including evidence references and "
        "degraded or unsupported posture markers."
    ),
    responses={
        200: {"description": "Workflow-pack task-flow checkpoints returned successfully."},
        404: {"description": "Unknown workflow-pack task-flow identifier."},
        503: {"description": "Workflow-pack task-flow store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_task_flow_checkpoints_route(
    task_flow_id: str,
) -> WorkflowPackTaskFlowCheckpointCatalogResponse:
    try:
        return build_workflow_pack_task_flow_checkpoint_catalog(task_flow_id)
    except WorkflowPackTaskFlowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/runs/{run_id}",
    response_model=WorkflowPackRunDetailResponse,
    operation_id="getWorkflowPackRunDetail",
    summary="Get lotus-ai workflow-pack run detail",
    description=(
        "Returns detailed workflow-pack run-ledger state, including recorded run history events."
    ),
    responses={
        200: {"description": "Workflow-pack run detail returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_detail_route(run_id: str) -> WorkflowPackRunDetailResponse:
    try:
        return build_workflow_pack_run_detail(run_id=run_id)
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/runs/{run_id}/source-events",
    response_model=WorkflowPackRunSourceEventResponse,
    operation_id="getWorkflowPackRunSourceEvents",
    summary="Get lotus-ai source events for one workflow-pack run",
    description=(
        "Returns the bounded AI-owned source-event projection for one workflow-pack run. This is "
        "source-lineage evidence for portfolio-memory consumers, not a raw output, prompt, or "
        "portfolio-memory reconstruction surface."
    ),
    responses={
        200: {"description": "Workflow-pack run source events returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_source_events_route(
    run_id: str,
) -> WorkflowPackRunSourceEventResponse:
    try:
        return build_workflow_pack_run_source_events(run_id=run_id)
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/runs/{run_id}/consumer-view",
    response_model=WorkflowPackRunConsumerViewResponse,
    operation_id="getWorkflowPackRunConsumerView",
    summary="Get lotus-ai workflow-pack run consumer view",
    description=(
        "Returns a bounded consumer-facing contract for one workflow-pack run, grouping runtime, "
        "review, lineage, and provenance posture without transferring downstream workflow authority."
    ),
    responses={
        200: {"description": "Workflow-pack run consumer view returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_consumer_view_route(
    run_id: str,
) -> WorkflowPackRunConsumerViewResponse:
    try:
        return build_workflow_pack_run_consumer_view(run_id=run_id)
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/platform/workflow-packs/runs/{run_id}/operator-profile",
    response_model=WorkflowPackRunOperatorProfileResponse,
    operation_id="getWorkflowPackRunOperatorProfile",
    summary="Get lotus-ai workflow-pack run operator profile",
    description=(
        "Returns one operator-facing workflow-pack run supportability profile, including runtime, "
        "review, supersession, artifact, and evidence posture for diagnosis."
    ),
    responses={
        200: {"description": "Workflow-pack run operator profile returned successfully."},
        404: {"description": "Unknown workflow-pack run identifier."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_workflow_pack_run_operator_profile_route(
    run_id: str,
) -> WorkflowPackRunOperatorProfileResponse:
    try:
        return build_workflow_pack_run_operator_profile(run_id=run_id)
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/runs/{run_id}/review-actions",
    response_model=WorkflowPackRunReviewActionResponse,
    operation_id="applyWorkflowPackRunReviewAction",
    summary="Apply a lotus-ai workflow-pack run review action",
    description=(
        "Records one bounded workflow-pack review-state action while preserving the separation "
        "between runtime execution posture and consequence-bearing downstream workflow authority."
    ),
    responses={
        200: {"description": "Workflow-pack run review action applied successfully."},
        403: {
            "description": "Caller is not currently authorized for workflow-pack review-state actions."
        },
        404: {"description": "Workflow-pack run or replacement run not found."},
        409: {
            "description": "Workflow-pack review-state action conflicts with the current run posture."
        },
        422: {"description": "Invalid review-state action payload."},
        503: {"description": "Workflow-pack run store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_workflow_pack_run_review_action_route(
    run_id: str,
    request: WorkflowPackRunReviewActionRequest,
) -> WorkflowPackRunReviewActionResponse:
    try:
        return apply_workflow_pack_run_review_action(run_id=run_id, request=request)
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/platform/workflow-packs/control-actions",
    response_model=WorkflowPackControlActionResponse,
    operation_id="applyWorkflowPackControlAction",
    summary="Apply a lotus-ai workflow-pack control action",
    description=(
        "Applies one bounded workflow-pack pause, resume, deprecate, or retire action and records the resulting control-plane event."
    ),
    responses={
        200: {"description": "Workflow-pack control action applied successfully."},
        403: {
            "description": "Caller is not currently authorized for workflow-pack control actions."
        },
        404: {"description": "Workflow-pack registration not found."},
        409: {
            "description": "Workflow-pack control action conflicts with the current registration state."
        },
        503: {"description": "Workflow-pack registry store is not ready."},
        500: {"description": "Unexpected server error."},
    },
)
async def apply_workflow_pack_control_action_route(
    request: WorkflowPackControlActionRequest,
) -> WorkflowPackControlActionResponse:
    try:
        return apply_workflow_pack_control_action(request)
    except WorkflowPackRegistryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
