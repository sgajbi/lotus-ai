from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    CallerLifecycleStatus,
    TenantPolicyMode,
)
from app.http.authenticated_caller import get_authenticated_caller
from app.services.caller_policy_store import get_caller_policy_repository


def require_active_registered_caller(
    caller_app: str,
    *,
    blocked_summary: str,
) -> None:
    authenticated_caller = get_authenticated_caller()
    if authenticated_caller is not None and authenticated_caller.caller_app != caller_app:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request caller_app does not match the authenticated HTTP caller identity.",
        )
    policy = get_caller_policy_repository().get_policy(caller_app)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=blocked_summary)
    if policy.lifecycle_status != CallerLifecycleStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=blocked_summary)


def authorize_request(
    *,
    caller_app: str,
    capability_type: AuthorizationCapabilityType,
    tenant_id: str | None = None,
    task_id: str | None = None,
    source_ids: list[str] | None = None,
) -> AuthorizationDecision:
    requested_source_ids = list(source_ids or [])
    authenticated_caller = get_authenticated_caller()
    identity_source = (
        authenticated_caller.trust_source if authenticated_caller else "body_metadata_only"
    )
    identity_bound = (
        authenticated_caller is not None and authenticated_caller.caller_app == caller_app
    )
    if authenticated_caller is not None and not identity_bound:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=authenticated_caller.caller_app,
            caller_identity_source=identity_source,
            caller_identity_bound=False,
            capability_type=capability_type,
            outcome=AuthorizationOutcome.BLOCKED_CALLER_IDENTITY_MISMATCH,
            allowed=False,
            tenant_policy_mode=TenantPolicyMode.OPTIONAL,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            summary=("Request caller_app does not match the authenticated HTTP caller identity."),
        )
    policy = get_caller_policy_repository().get_policy(caller_app)
    if policy is None:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=(
                authenticated_caller.caller_app if authenticated_caller else None
            ),
            caller_identity_source=identity_source,
            caller_identity_bound=identity_bound,
            capability_type=capability_type,
            outcome=AuthorizationOutcome.BLOCKED_UNKNOWN_CALLER,
            allowed=False,
            tenant_policy_mode=TenantPolicyMode.OPTIONAL,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            summary=(
                f"Caller '{caller_app}' is not registered in the caller policy registry and is "
                "blocked by default."
            ),
        )

    if policy.lifecycle_status != CallerLifecycleStatus.ACTIVE:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=(
                authenticated_caller.caller_app if authenticated_caller else None
            ),
            caller_identity_source=identity_source,
            caller_identity_bound=identity_bound,
            capability_type=capability_type,
            outcome=AuthorizationOutcome.BLOCKED_CALLER_DISABLED,
            allowed=False,
            tenant_policy_mode=policy.tenant_policy_mode,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            summary=(
                f"Caller '{caller_app}' is registered but currently disabled for protected "
                "lotus-ai execution paths."
            ),
        )

    if capability_type == AuthorizationCapabilityType.ASYNC_CONTROL:
        return _evaluate_control_capability(
            caller_app=caller_app,
            capability_type=capability_type,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            tenant_policy_mode=policy.tenant_policy_mode,
            allowed=policy.allow_async_control,
            blocked_outcome=AuthorizationOutcome.BLOCKED_ASYNC_CONTROL_NOT_ALLOWED,
            blocked_summary=(
                f"Caller '{caller_app}' is not authorized for async control-plane actions."
            ),
            allowed_summary=(
                f"Caller '{caller_app}' is authorized for async control-plane actions under the "
                "current caller policy registry."
            ),
        )

    if capability_type == AuthorizationCapabilityType.PROMPT_CONTROL:
        return _evaluate_control_capability(
            caller_app=caller_app,
            capability_type=capability_type,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            tenant_policy_mode=policy.tenant_policy_mode,
            allowed=policy.allow_prompt_control,
            blocked_outcome=AuthorizationOutcome.BLOCKED_PROMPT_CONTROL_NOT_ALLOWED,
            blocked_summary=(
                f"Caller '{caller_app}' is not authorized for prompt control-plane actions."
            ),
            allowed_summary=(
                f"Caller '{caller_app}' is authorized for prompt control-plane actions under the "
                "current caller policy registry."
            ),
        )

    if capability_type == AuthorizationCapabilityType.PROVIDER_CONTROL:
        return _evaluate_control_capability(
            caller_app=caller_app,
            capability_type=capability_type,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            tenant_policy_mode=policy.tenant_policy_mode,
            allowed=policy.allow_provider_control,
            blocked_outcome=AuthorizationOutcome.BLOCKED_PROVIDER_CONTROL_NOT_ALLOWED,
            blocked_summary=(
                f"Caller '{caller_app}' is not authorized for provider control-plane actions."
            ),
            allowed_summary=(
                f"Caller '{caller_app}' is authorized for provider control-plane actions under "
                "the current caller policy registry."
            ),
        )

    tenant_decision = _evaluate_tenant_policy(
        caller_app=caller_app,
        tenant_id=tenant_id,
        capability_type=capability_type,
        task_id=task_id,
        requested_source_ids=requested_source_ids,
        tenant_policy_mode=policy.tenant_policy_mode,
        restricted_tenant_ids=policy.restricted_tenant_ids,
    )
    if tenant_decision is not None:
        return tenant_decision

    if capability_type == AuthorizationCapabilityType.TASK_EXECUTION:
        if task_id not in policy.allowed_task_ids:
            return AuthorizationDecision(
                caller_app=caller_app,
                authenticated_caller_app=(
                    authenticated_caller.caller_app if authenticated_caller else None
                ),
                caller_identity_source=identity_source,
                caller_identity_bound=identity_bound,
                capability_type=capability_type,
                outcome=AuthorizationOutcome.BLOCKED_TASK_NOT_ALLOWED,
                allowed=False,
                tenant_policy_mode=policy.tenant_policy_mode,
                task_id=task_id,
                requested_source_ids=requested_source_ids,
                tenant_id=tenant_id,
                summary=(f"Caller '{caller_app}' is not authorized to execute task '{task_id}'."),
            )
        if task_id in {"knowledge_search.v1", "knowledge_answer.v1"} or requested_source_ids:
            source_decision = _evaluate_retrieval_sources(
                caller_app=caller_app,
                capability_type=capability_type,
                task_id=task_id,
                requested_source_ids=requested_source_ids,
                allowed_source_ids=policy.allowed_retrieval_source_ids,
                tenant_id=tenant_id,
                tenant_policy_mode=policy.tenant_policy_mode,
            )
            if source_decision is not None:
                return source_decision
        effective_source_ids = (
            requested_source_ids or list(policy.allowed_retrieval_source_ids)
            if task_id in {"knowledge_search.v1", "knowledge_answer.v1"}
            else []
        )
        return _allowed_decision(
            caller_app=caller_app,
            capability_type=capability_type,
            tenant_id=tenant_id,
            task_id=task_id,
            tenant_policy_mode=policy.tenant_policy_mode,
            requested_source_ids=requested_source_ids,
            effective_source_ids=effective_source_ids,
            summary=(
                f"Caller '{caller_app}' is authorized for task '{task_id}' under the current "
                "caller policy registry."
            ),
        )

    if capability_type == AuthorizationCapabilityType.RETRIEVAL_EXECUTION:
        source_decision = _evaluate_retrieval_sources(
            caller_app=caller_app,
            capability_type=capability_type,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            allowed_source_ids=policy.allowed_retrieval_source_ids,
            tenant_id=tenant_id,
            tenant_policy_mode=policy.tenant_policy_mode,
        )
        if source_decision is not None:
            return source_decision
        effective_source_ids = requested_source_ids or list(policy.allowed_retrieval_source_ids)
        return _allowed_decision(
            caller_app=caller_app,
            capability_type=capability_type,
            tenant_id=tenant_id,
            task_id=task_id,
            tenant_policy_mode=policy.tenant_policy_mode,
            requested_source_ids=requested_source_ids,
            effective_source_ids=effective_source_ids,
            summary=(
                f"Caller '{caller_app}' is authorized to search the approved retrieval corpus."
            ),
        )

    if capability_type == AuthorizationCapabilityType.LIVE_PROVIDER_EXECUTION:
        if not policy.allow_live_provider:
            return AuthorizationDecision(
                caller_app=caller_app,
                authenticated_caller_app=(
                    authenticated_caller.caller_app if authenticated_caller else None
                ),
                caller_identity_source=identity_source,
                caller_identity_bound=identity_bound,
                capability_type=capability_type,
                outcome=AuthorizationOutcome.BLOCKED_LIVE_PROVIDER_NOT_ALLOWED,
                allowed=False,
                tenant_policy_mode=policy.tenant_policy_mode,
                task_id=task_id,
                requested_source_ids=requested_source_ids,
                tenant_id=tenant_id,
                summary=(f"Caller '{caller_app}' is not authorized for live provider execution."),
            )
        return _allowed_decision(
            caller_app=caller_app,
            capability_type=capability_type,
            tenant_id=tenant_id,
            task_id=task_id,
            tenant_policy_mode=policy.tenant_policy_mode,
            requested_source_ids=requested_source_ids,
            effective_source_ids=[],
            summary=(
                f"Caller '{caller_app}' is authorized for live provider execution under the "
                "current caller policy registry."
            ),
        )

    raise RuntimeError(f"Unsupported authorization capability type: {capability_type.value}")


def require_authorized(decision: AuthorizationDecision) -> AuthorizationDecision:
    if decision.allowed:
        return decision
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.summary)


def _evaluate_tenant_policy(
    *,
    caller_app: str,
    tenant_id: str | None,
    capability_type: AuthorizationCapabilityType,
    task_id: str | None,
    requested_source_ids: list[str],
    tenant_policy_mode: TenantPolicyMode,
    restricted_tenant_ids: list[str],
) -> AuthorizationDecision | None:
    authenticated_caller = get_authenticated_caller()
    identity_source = (
        authenticated_caller.trust_source if authenticated_caller else "body_metadata_only"
    )
    identity_bound = (
        authenticated_caller is not None and authenticated_caller.caller_app == caller_app
    )
    if tenant_policy_mode == TenantPolicyMode.OPTIONAL:
        return None
    if tenant_id is None:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=(
                authenticated_caller.caller_app if authenticated_caller else None
            ),
            caller_identity_source=identity_source,
            caller_identity_bound=identity_bound,
            capability_type=capability_type,
            outcome=AuthorizationOutcome.BLOCKED_TENANT_REQUIRED,
            allowed=False,
            tenant_policy_mode=tenant_policy_mode,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=None,
            summary=(
                f"Caller '{caller_app}' must supply tenant_id under the current access-control "
                "policy."
            ),
        )
    if tenant_policy_mode == TenantPolicyMode.RESTRICTED and tenant_id not in restricted_tenant_ids:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=(
                authenticated_caller.caller_app if authenticated_caller else None
            ),
            caller_identity_source=identity_source,
            caller_identity_bound=identity_bound,
            capability_type=capability_type,
            outcome=AuthorizationOutcome.BLOCKED_TENANT_NOT_ALLOWED,
            allowed=False,
            tenant_policy_mode=tenant_policy_mode,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            summary=(
                f"Tenant '{tenant_id}' is not authorized for caller '{caller_app}' under the "
                "current access-control policy."
            ),
        )
    return None


def _evaluate_retrieval_sources(
    *,
    caller_app: str,
    capability_type: AuthorizationCapabilityType,
    task_id: str | None,
    requested_source_ids: list[str],
    allowed_source_ids: list[str],
    tenant_id: str | None,
    tenant_policy_mode: TenantPolicyMode,
) -> AuthorizationDecision | None:
    authenticated_caller = get_authenticated_caller()
    identity_source = (
        authenticated_caller.trust_source if authenticated_caller else "body_metadata_only"
    )
    identity_bound = (
        authenticated_caller is not None and authenticated_caller.caller_app == caller_app
    )
    allowed_source_id_set = set(allowed_source_ids)
    if requested_source_ids:
        if not set(requested_source_ids).issubset(allowed_source_id_set):
            return AuthorizationDecision(
                caller_app=caller_app,
                authenticated_caller_app=(
                    authenticated_caller.caller_app if authenticated_caller else None
                ),
                caller_identity_source=identity_source,
                caller_identity_bound=identity_bound,
                capability_type=capability_type,
                outcome=AuthorizationOutcome.BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED,
                allowed=False,
                tenant_policy_mode=tenant_policy_mode,
                task_id=task_id,
                requested_source_ids=requested_source_ids,
                tenant_id=tenant_id,
                summary=(
                    f"Caller '{caller_app}' requested retrieval sources outside its approved "
                    "policy scope."
                ),
            )
        return None
    if not allowed_source_ids:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=(
                authenticated_caller.caller_app if authenticated_caller else None
            ),
            caller_identity_source=identity_source,
            caller_identity_bound=identity_bound,
            capability_type=capability_type,
            outcome=AuthorizationOutcome.BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED,
            allowed=False,
            tenant_policy_mode=tenant_policy_mode,
            task_id=task_id,
            requested_source_ids=[],
            tenant_id=tenant_id,
            summary=(
                f"Caller '{caller_app}' has no approved retrieval sources under the current "
                "access-control policy."
            ),
        )
    return None


def _allowed_decision(
    *,
    caller_app: str,
    capability_type: AuthorizationCapabilityType,
    tenant_id: str | None,
    task_id: str | None,
    tenant_policy_mode: TenantPolicyMode,
    requested_source_ids: list[str],
    effective_source_ids: list[str],
    summary: str,
) -> AuthorizationDecision:
    authenticated_caller = get_authenticated_caller()
    return AuthorizationDecision(
        caller_app=caller_app,
        authenticated_caller_app=(
            authenticated_caller.caller_app if authenticated_caller else None
        ),
        caller_identity_source=(
            authenticated_caller.trust_source if authenticated_caller else "body_metadata_only"
        ),
        caller_identity_bound=(
            authenticated_caller is not None and authenticated_caller.caller_app == caller_app
        ),
        capability_type=capability_type,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=tenant_policy_mode,
        task_id=task_id,
        requested_source_ids=requested_source_ids,
        effective_source_ids=effective_source_ids,
        tenant_id=tenant_id,
        summary=summary,
    )


def _evaluate_control_capability(
    *,
    caller_app: str,
    capability_type: AuthorizationCapabilityType,
    task_id: str | None,
    requested_source_ids: list[str],
    tenant_id: str | None,
    tenant_policy_mode: TenantPolicyMode,
    allowed: bool,
    blocked_outcome: AuthorizationOutcome,
    blocked_summary: str,
    allowed_summary: str,
) -> AuthorizationDecision:
    authenticated_caller = get_authenticated_caller()
    identity_source = (
        authenticated_caller.trust_source if authenticated_caller else "body_metadata_only"
    )
    identity_bound = (
        authenticated_caller is not None and authenticated_caller.caller_app == caller_app
    )
    if not allowed:
        return AuthorizationDecision(
            caller_app=caller_app,
            authenticated_caller_app=(
                authenticated_caller.caller_app if authenticated_caller else None
            ),
            caller_identity_source=identity_source,
            caller_identity_bound=identity_bound,
            capability_type=capability_type,
            outcome=blocked_outcome,
            allowed=False,
            tenant_policy_mode=tenant_policy_mode,
            task_id=task_id,
            requested_source_ids=requested_source_ids,
            tenant_id=tenant_id,
            summary=blocked_summary,
        )
    return _allowed_decision(
        caller_app=caller_app,
        capability_type=capability_type,
        tenant_id=tenant_id,
        task_id=task_id,
        tenant_policy_mode=tenant_policy_mode,
        requested_source_ids=requested_source_ids,
        effective_source_ids=[],
        summary=allowed_summary,
    )
