from __future__ import annotations

from app.config import settings
from app.contracts.access_control import (
    AccessControlGovernanceStatusResponse,
)
from app.services.access_control_activation_readiness import (
    build_access_control_activation_readiness,
)
from app.services.readiness_catalog import (
    build_access_control_runbook_readiness,
)
from app.services.access_control_runtime import build_access_control_runtime_status
from app.services.caller_policy_store import get_caller_policy_repository
from app.services.governance_readiness import summarize_governance_flags


def build_access_control_governance_status() -> AccessControlGovernanceStatusResponse:
    policies = get_caller_policy_repository().list_policies()
    restricted_tenant_policy_count = sum(1 for policy in policies if policy.restricted_tenant_ids)
    runtime = build_access_control_runtime_status()
    activation_readiness = build_access_control_activation_readiness()
    runbook_readiness = build_access_control_runbook_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
    )
    return AccessControlGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        store_mode=settings.access_control_store_mode,
        enforcement_state=runtime.enforcement_state,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        policy_count=len(policies),
        tenant_restricted_policy_count=restricted_tenant_policy_count,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            "Caller-app registry entries now define bounded task, retrieval, live-provider, async-control, prompt-control, and provider-control capability posture in one inspectable policy surface.",
            (
                "Activation readiness is satisfied because SQL-backed caller policy storage and full protected-surface enforcement are both active."
                if activation_readiness.activation_ready
                else "Activation readiness is still blocked until caller policy storage is durable and the fully enforced posture remains restart-safe."
            ),
            (
                "Runbook readiness is complete for caller onboarding, revocation, tenant restriction changes, blocked-authorization review, and emergency-override posture."
                if runbook_readiness.runbook_ready
                else "Runbook readiness is incomplete for at least one required access-control operational path."
            ),
        ],
    )
