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
    enforcement_state = (
        AccessControlEnforcementState.POLICY_RESOLUTION_READY
        if settings.access_control_store_mode == "sqlalchemy"
        else AccessControlEnforcementState.DOCUMENTARY_ONLY
    )
    return AccessControlRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.access_control_store_mode,
        store=get_access_control_store_runtime_status(),
        enforcement_state=enforcement_state,
        unknown_caller_policy=(
            "Unknown callers resolve to an explicit deny policy, but protected request paths are not yet broadly enforced in Slice 1."
        ),
        tenant_isolation_active=False,
        policy_count=len(policies),
        protected_surface_count=_PROTECTED_SURFACE_COUNT,
        status_summary=[
            "Caller registry and capability policy resolution are now explicit and durable through a dedicated access-control store seam.",
            (
                "SQL-backed caller policy storage is active; policy resolution is restart-safe, but broad request blocking is intentionally deferred to later slices."
                if settings.access_control_store_mode == "sqlalchemy"
                else "Memory-backed caller policy storage is active for foundation posture; policy resolution is visible but not restart-safe."
            ),
            "Tenant restrictions are modeled in the registry, but tenant-bound request blocking is not active yet in Slice 1.",
        ],
    )
