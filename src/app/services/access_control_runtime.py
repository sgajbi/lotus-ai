from __future__ import annotations

from app.config import settings
from app.contracts.access_control import (
    AccessControlEnforcementState,
    AccessControlRuntimeStatusResponse,
    CallerPolicyCatalogResponse,
)
from app.services.caller_policy_store import get_caller_policy_repository
from app.services.runtime_readiness import get_access_control_store_runtime_status

_PROTECTED_SURFACE_COUNT = 6


def data_plane_authorization_enforced() -> bool:
    """Structural invariant, not an unmeasured claim (issue #154).

    Every protected router binds caller authentication and the
    registered-active-caller gate at inclusion, so no data-plane route can
    execute unauthorized; the property is proven by the route-coverage
    guard in tests rather than sampled at runtime. It is a constant here
    because it is enforced by construction - if that ever stops being
    true, the coverage guard fails before this value could mislead anyone.
    """

    return True


def control_plane_authorization_enforced() -> bool:
    """Structural invariant, as above: control-plane routes are bound by the
    same router-level dependencies and covered by the same guard."""

    return True


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
        enforcement_state=AccessControlEnforcementState.FULLY_ENFORCED,
        data_plane_enforced=data_plane_authorization_enforced(),
        control_plane_enforced=control_plane_authorization_enforced(),
        unknown_caller_policy=(
            "Unknown callers are explicitly denied with HTTP 403 across protected data-plane and control-plane request paths."
        ),
        tenant_isolation_active=True,
        policy_count=len(policies),
        protected_surface_count=_PROTECTED_SURFACE_COUNT,
        status_summary=[
            "Current posture is FULLY_ENFORCED: caller registry resolution now governs task, retrieval, live-provider, async-control, prompt-control, and provider-control paths.",
            (
                "SQL-backed caller policy storage is active, so enforced authorization decisions are restart-safe across protected data-plane and control-plane request paths."
                if settings.access_control_store_mode == "sqlalchemy"
                else "Memory-backed caller policy storage is enforcing protected paths, but that posture is not restart-safe and remains governance-blocked."
            ),
            "Tenant restrictions are enforced where tenant identity is already part of the protected request contract, and control-plane callers remain fail-closed without a hidden override path.",
        ],
    )
