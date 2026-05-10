from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.tasks import TaskExecutionResponse
from app.contracts.workflow_packs import (
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackExecutionRequest,
    WorkflowPackExecutionResponse,
)
from app.contracts.workflow_pack_runs import WorkflowPackRunDescriptor
from app.services.task_execution_pipeline import (
    build_failed_task_execution_response,
    build_task_execution_response,
    persist_task_execution_audit,
    resolve_task_execution,
    validate_task_request,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
from app.services.workflow_pack_bindings import (
    WorkflowPackExecutionBinding,
    get_workflow_pack_execution_binding,
    get_resolved_workflow_pack_execution_binding,
)
from app.services.workflow_pack_run_ledger import (
    ensure_workflow_pack_run_store_ready,
    record_registered_workflow_pack_run,
)
from app.services.workflow_pack_task_flow_recording import (
    record_task_flow_for_workflow_pack_run,
)
from app.services.workflow_pack_task_flow_service import (
    ensure_workflow_pack_task_flow_store_ready,
)
from app.services.workflow_pack_queue_admission import workflow_pack_queue_admission
from app.services.outcome_review_narrative_guardrails import (
    validate_outcome_review_narrative_payload,
)
from app.services.operations_handoff_summary_guardrails import (
    validate_operations_handoff_summary_payload,
)
from app.services.proof_pack_pm_memo_guardrails import validate_proof_pack_pm_memo_payload
from app.services.wave_pm_memo_guardrails import validate_wave_pm_memo_payload


def execute_workflow_pack(request: WorkflowPackExecutionRequest) -> WorkflowPackExecutionResponse:
    binding = get_workflow_pack_execution_binding(pack_id=request.pack_id, version=request.version)
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Explicit workflow-pack execution is not implemented for "
                f"{request.pack_id}@{request.version}."
            ),
        )
    resolved_binding = get_resolved_workflow_pack_execution_binding(
        pack_id=request.pack_id,
        version=request.version,
    )
    if resolved_binding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack registration: {request.pack_id}@{request.version}",
        )
    registration = resolved_binding.registration

    workflow_surface = request.workflow_surface or binding.default_workflow_surface
    eligibility = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id=request.pack_id,
            version=request.version,
            caller_app=request.task_request.caller.caller_app,
            environment=request.environment,
            caller_identity_class=request.caller_identity_class,
            tenant_id=request.task_request.caller.tenant_id,
            workflow_surface=workflow_surface,
        )
    )
    if not eligibility.allowed:
        detail = (
            eligibility.denial_reasons[0]
            if eligibility.denial_reasons
            else ("Workflow-pack execution is not currently allowed.")
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    validate_workflow_pack_execution_binding(request=request, binding=binding)

    context = validate_task_request(request.task_request)
    ensure_workflow_pack_run_store_ready()
    ensure_workflow_pack_task_flow_store_ready()
    with workflow_pack_queue_admission(
        registration=registration,
        requested_lane=request.queue_lane,
        caller_app=request.task_request.caller.caller_app,
        correlation_id=request.task_request.caller.correlation_id,
        tenant_id=request.task_request.caller.tenant_id,
        workflow_surface=workflow_surface,
        task_request=request.task_request,
        environment=request.environment,
        caller_identity_class=request.caller_identity_class,
    ):
        try:
            resolved = resolve_task_execution(context=context)
            response = build_task_execution_response(resolved=resolved)
        except HTTPException as exc:
            response = build_failed_task_execution_response(context=context, exc=exc)
        persist_task_execution_audit(context=context, response=response)
        workflow_pack_run = record_registered_workflow_pack_run(
            context=context,
            response=response,
            registration=registration,
            workflow_surface=workflow_surface,
        )
        record_task_flow_for_workflow_pack_run(
            context=context,
            registration=registration,
            workflow_surface=workflow_surface,
            workflow_pack_run=workflow_pack_run,
        )
    response = _attach_workflow_pack_run_id(response=response, workflow_pack_run=workflow_pack_run)

    return WorkflowPackExecutionResponse(
        service=settings.service_name,
        version=settings.service_version,
        eligibility=eligibility,
        execution=response,
        workflow_pack_run=workflow_pack_run,
        summary=[
            f"Executed workflow pack `{request.pack_id}@{request.version}` through the explicit workflow-pack execution seam.",
            "The bounded task pipeline remains the execution substrate, but registration, eligibility, and run recording are now explicit rather than inferred only from the task path.",
        ],
    )


def validate_workflow_pack_execution_binding(
    *,
    request: WorkflowPackExecutionRequest,
    binding: WorkflowPackExecutionBinding,
) -> None:
    if request.task_request.task_id != binding.task_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{request.pack_id}@{request.version} currently binds to {binding.task_id} only.",
        )
    if not binding.validate_task_request_payload(payload=request.task_request.context.payload):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{request.pack_id}@{request.version} requires the bound workflow-pack source "
                "payload sections declared for its current execution binding."
            ),
        )
    if request.pack_id == "outcome_review_narrative.pack" and request.version == "v1":
        validate_outcome_review_narrative_payload(request.task_request.context.payload)
    if request.pack_id == "dpm_pm_memo.pack" and request.version == "v1":
        validate_proof_pack_pm_memo_payload(request.task_request.context.payload)
    if request.pack_id == "dpm_wave_pm_memo.pack" and request.version == "v1":
        validate_wave_pm_memo_payload(request.task_request.context.payload)
    if request.pack_id == "dpm_operations_handoff_summary.pack" and request.version == "v1":
        validate_operations_handoff_summary_payload(request.task_request.context.payload)


def _attach_workflow_pack_run_id(
    *,
    response: TaskExecutionResponse,
    workflow_pack_run: WorkflowPackRunDescriptor,
) -> TaskExecutionResponse:
    return response.model_copy(
        update={
            "audit": response.audit.model_copy(
                update={"workflow_pack_run_id": workflow_pack_run.run_id}
            )
        }
    )
