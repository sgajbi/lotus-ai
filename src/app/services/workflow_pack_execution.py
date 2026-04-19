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
    build_task_execution_response,
    persist_task_execution_audit,
    resolve_task_execution,
    validate_task_request,
)
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_run_ledger import record_registered_workflow_pack_run


def execute_workflow_pack(request: WorkflowPackExecutionRequest) -> WorkflowPackExecutionResponse:
    registration = get_workflow_pack_registration(pack_id=request.pack_id, version=request.version)
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack registration: {request.pack_id}@{request.version}",
        )

    eligibility = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id=request.pack_id,
            version=request.version,
            caller_app=request.task_request.caller.caller_app,
            environment=request.environment,
            caller_identity_class=request.caller_identity_class,
            tenant_id=request.task_request.caller.tenant_id,
            workflow_surface=request.workflow_surface,
        )
    )
    if not eligibility.allowed:
        detail = eligibility.denial_reasons[0] if eligibility.denial_reasons else (
            "Workflow-pack execution is not currently allowed."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    _validate_execution_binding(request=request)

    context = validate_task_request(request.task_request)
    resolved = resolve_task_execution(context=context)
    response = build_task_execution_response(resolved=resolved)
    persist_task_execution_audit(context=context, response=response)
    workflow_pack_run = record_registered_workflow_pack_run(
        context=context,
        response=response,
        registration=registration,
        workflow_surface=request.workflow_surface,
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


def _validate_execution_binding(*, request: WorkflowPackExecutionRequest) -> None:
    if request.pack_id == "advisor_brief.pack" and request.version == "v1":
        if request.task_request.task_id != "explain.v1":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="advisor_brief.pack@v1 currently binds to explain.v1 only.",
            )
        payload = request.task_request.context.payload
        if not {"portfolio", "period", "performance", "supportability"}.issubset(payload.keys()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "advisor_brief.pack@v1 requires the advisor-brief source payload with "
                    "portfolio, period, performance, and supportability sections."
                ),
            )
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Explicit workflow-pack execution is not implemented for "
            f"{request.pack_id}@{request.version}."
        ),
    )


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
