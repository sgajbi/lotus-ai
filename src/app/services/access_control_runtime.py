from __future__ import annotations

from app.config import settings
from app.contracts.access_control import (
    AccessControlEnforcementState,
    AccessControlRuntimeStatusResponse,
    CallerPolicyCatalogResponse,
)
from app.services.caller_policy_store import get_caller_policy_repository
from app.services.runtime_readiness import get_access_control_store_runtime_status

_PROTECTED_SURFACE_COUNT = 5


def list_caller_policies() -> CallerPolicyCatalogResponse:
    policies = get_caller_policy_repository().list_policies()
    return CallerPolicyCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.access_control_store_mode,
        policy_count=len(policies),
        policies=policies,
    )


def build_access_control_runtime_status() -> AccessControlRuntimeStatusResponse:
    policies = get_caller_policy_repository().list_policies()
    return AccessControlRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.access_control_store_mode,
        store=get_access_control_store_runtime_status(),
        enforcement_state=AccessControlEnforcementState.ENFORCED,
        unknown_caller_policy=(
            "Unknown callers are explicitly denied with HTTP 403 across protected data-plane request paths."
        ),
        tenant_isolation_active=True,
        policy_count=len(policies),
        protected_surface_count=_PROTECTED_SURFACE_COUNT,
        status_summary=[
            "Caller registry resolution and data-plane authorization enforcement are both active for task, retrieval, and live-provider execution paths.",
            (
                "SQL-backed caller policy storage is active, so enforced authorization decisions are restart-safe across protected data-plane request paths."
                if settings.access_control_store_mode == "sqlalchemy"
                else "Memory-backed caller policy storage is enforcing protected data-plane request paths, but that posture is not restart-safe and remains governance-blocked."
            ),
            "Tenant restrictions are now enforced where tenant identity is already part of the task and live-provider request contracts.",
        ],
    )
