from __future__ import annotations

from app.config import settings
from app.contracts.access_control import (
    AccessControlEnforcementState,
    AccessControlGovernanceStatusResponse,
)
from app.services.caller_policy_store import get_caller_policy_repository


def build_access_control_governance_status() -> AccessControlGovernanceStatusResponse:
    policies = get_caller_policy_repository().list_policies()
    restricted_tenant_policy_count = sum(1 for policy in policies if policy.restricted_tenant_ids)
    governance_ready = settings.access_control_store_mode == "sqlalchemy"
    return AccessControlGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        store_mode=settings.access_control_store_mode,
        enforcement_state=(
            AccessControlEnforcementState.POLICY_RESOLUTION_READY
            if governance_ready
            else AccessControlEnforcementState.DOCUMENTARY_ONLY
        ),
        policy_count=len(policies),
        tenant_restricted_policy_count=restricted_tenant_policy_count,
        blocking_area_count=0 if governance_ready else 1,
        governance_summary=[
            "Caller-app registry entries now define bounded task, retrieval, live-provider, and control-plane capability posture in one inspectable policy surface.",
            (
                "Access-control policy storage is SQL-backed and restart-safe, so later enforcement slices can build on a durable registry."
                if governance_ready
                else "Access-control policy storage is still memory-backed, so the registry remains documentary and not restart-safe."
            ),
            "Unknown-caller deny posture and tenant restriction intent are explicit, but broad enforcement is intentionally deferred to later slices.",
        ],
    )
