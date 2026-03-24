from __future__ import annotations

from app.config import settings
from app.contracts.use_cases import (
    FirstUseCaseGovernanceStatusResponse,
    FirstUseCaseOperationalPosture,
)
from app.services.first_use_case_readiness import build_first_use_case_readiness
from app.services.first_use_case_runbook_readiness import build_first_use_case_runbook_readiness
from app.services.governance_readiness import summarize_governance_flags


def build_first_use_case_governance_status() -> FirstUseCaseGovernanceStatusResponse:
    readiness = build_first_use_case_readiness()
    runbook_readiness = build_first_use_case_runbook_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        readiness.readiness_ready,
        runbook_readiness.runbook_ready,
    )
    operational_posture = (
        FirstUseCaseOperationalPosture.LIMITED_ROLLOUT_READY
        if governance_ready
        else FirstUseCaseOperationalPosture.LIMITED_ROLLOUT_BLOCKED
    )
    return FirstUseCaseGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        use_case_id=readiness.use_case_id,
        downstream_app=readiness.downstream_app,
        operational_posture=operational_posture,
        governance_ready=governance_ready,
        readiness=readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            "The first production use case remains a bounded lotus-performance analytics-commentary path over caller-supplied structured facts rather than a broad downstream rollout.",
            (
                "Limited rollout is governance-ready because runtime evidence, durable support review, and runbook ownership are all in place."
                if governance_ready
                else "Limited rollout remains governance-blocked until both the bounded readiness surface and the first-use-case runbook surface report ready."
            ),
            (
                "Rollback posture is explicit: when first-use-case governance is no longer ready, downstream activation should be treated as blocked until the bounded contract and support signals recover."
            ),
        ],
    )
