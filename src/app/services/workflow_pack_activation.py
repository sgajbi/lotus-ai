from __future__ import annotations

from app.config import settings
from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackEligibilityEvaluationResponse,
    WorkflowPackEligibilityResult,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationStatus,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration


def evaluate_workflow_pack_eligibility(
    request: WorkflowPackEligibilityEvaluationRequest,
) -> WorkflowPackEligibilityEvaluationResponse:
    registration = get_workflow_pack_registration(pack_id=request.pack_id, version=request.version)
    if registration is None:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_NOT_REGISTERED,
            denial_reasons=[
                "The requested workflow-pack version does not exist in the governed registry."
            ],
            evaluated_registration_ref=None,
            tenant_scope_applied=False,
            workflow_surface_applied=False,
            status_summary=[
                "Workflow-pack execution remains deny-by-default for unknown pack versions.",
            ],
        )

    registration_ref = _build_registration_ref(registration)
    tenant_scope_applied = bool(registration.tenant_scope)
    workflow_surface_applied = bool(registration.surface_scope)
    if registration.registration_status != WorkflowPackRegistrationStatus.REGISTERED:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_VALIDATION_STATUS,
            denial_reasons=[
                "The workflow-pack version is not in REGISTERED posture and cannot enter activation evaluation."
            ],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Discovery, validation-failed, withdrawn, and retired records remain non-executable even when visible in the registry.",
            ],
        )

    if registration.activation_state == WorkflowPackActivationState.RETIRED:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_RETIRED,
            denial_reasons=["The workflow-pack version is retired and cannot be executed."],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Retired workflow-pack versions remain inspectable but are never executable.",
            ],
        )

    if (
        registration.pause_state != "NOT_PAUSED"
        or registration.activation_state == WorkflowPackActivationState.PAUSED
    ):
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_PAUSED,
            denial_reasons=[
                "The workflow-pack version is paused and execution is temporarily blocked."
            ],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Pause state short-circuits normal activation evaluation so operators have a clean kill switch.",
            ],
        )

    if registration.activation_state == WorkflowPackActivationState.DARK:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_NOT_ACTIVE,
            denial_reasons=[
                "The workflow-pack version is registered but not active for execution."
            ],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Dark workflow-pack versions remain known to the registry without becoming runnable.",
            ],
        )

    if request.caller_app not in registration.supported_callers:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_CALLER_SCOPE,
            denial_reasons=["The caller application is outside the supported workflow-pack scope."],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Caller scope remains explicit so downstream applications cannot silently self-enable workflow packs.",
            ],
        )

    if request.environment not in registration.supported_environments:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_ENVIRONMENT_SCOPE,
            denial_reasons=[
                "The requested environment is outside the supported workflow-pack scope."
            ],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Environment scope remains explicit so non-production posture does not leak into production by implication.",
            ],
        )

    if request.caller_identity_class not in registration.supported_identity_classes:
        return _build_denied_response(
            request=request,
            result=WorkflowPackEligibilityResult.DENIED_CALLER_SCOPE,
            denial_reasons=[
                "The caller identity class is outside the supported workflow-pack scope."
            ],
            evaluated_registration_ref=registration_ref,
            tenant_scope_applied=tenant_scope_applied,
            workflow_surface_applied=workflow_surface_applied,
            status_summary=[
                "Identity-class scope remains bounded and is evaluated separately from caller-application scope.",
            ],
        )

    if registration.tenant_scope:
        if request.tenant_id is None or request.tenant_id not in registration.tenant_scope:
            return _build_denied_response(
                request=request,
                result=WorkflowPackEligibilityResult.DENIED_TENANT_SCOPE,
                denial_reasons=["The tenant is outside the supported workflow-pack scope."],
                evaluated_registration_ref=registration_ref,
                tenant_scope_applied=tenant_scope_applied,
                workflow_surface_applied=workflow_surface_applied,
                status_summary=[
                    "Tenant-scoped workflow-pack activation remains deny-by-default when tenant scope is declared.",
                ],
            )

    if registration.surface_scope:
        if (
            request.workflow_surface is None
            or request.workflow_surface not in registration.surface_scope
        ):
            return _build_denied_response(
                request=request,
                result=WorkflowPackEligibilityResult.DENIED_SURFACE_SCOPE,
                denial_reasons=[
                    "The workflow surface is outside the supported workflow-pack scope."
                ],
                evaluated_registration_ref=registration_ref,
                tenant_scope_applied=tenant_scope_applied,
                workflow_surface_applied=workflow_surface_applied,
                status_summary=[
                    "Workflow-surface scope remains explicit so one application cannot expose a pack on every surface by default.",
                ],
            )

    return WorkflowPackEligibilityEvaluationResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack_id=request.pack_id,
        requested_version=request.version,
        eligibility_result=WorkflowPackEligibilityResult.ALLOWED,
        allowed=True,
        evaluated_registration_ref=registration_ref,
        caller_app=request.caller_app,
        environment=request.environment,
        caller_identity_class=request.caller_identity_class,
        tenant_scope_applied=tenant_scope_applied,
        workflow_surface_applied=workflow_surface_applied,
        denial_reasons=[],
        status_summary=[
            "The workflow-pack version is registered, active, and within the declared caller, environment, and surface scope.",
            "This response is the bounded activation decision and does not grant downstream systems authority over business workflow consequences.",
        ],
    )


def _build_denied_response(
    *,
    request: WorkflowPackEligibilityEvaluationRequest,
    result: WorkflowPackEligibilityResult,
    denial_reasons: list[str],
    evaluated_registration_ref: str | None,
    tenant_scope_applied: bool,
    workflow_surface_applied: bool,
    status_summary: list[str],
) -> WorkflowPackEligibilityEvaluationResponse:
    return WorkflowPackEligibilityEvaluationResponse(
        service=settings.service_name,
        version=settings.service_version,
        pack_id=request.pack_id,
        requested_version=request.version,
        eligibility_result=result,
        allowed=False,
        evaluated_registration_ref=evaluated_registration_ref,
        caller_app=request.caller_app,
        environment=request.environment,
        caller_identity_class=request.caller_identity_class,
        tenant_scope_applied=tenant_scope_applied,
        workflow_surface_applied=workflow_surface_applied,
        denial_reasons=denial_reasons,
        status_summary=status_summary,
    )


def _build_registration_ref(registration: WorkflowPackRegistrationDescriptor) -> str:
    return f"{registration.pack_id}@{registration.version}"
