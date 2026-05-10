from __future__ import annotations

from app.config import settings
from app.contracts.access_control import AccessControlGovernanceStatusResponse
from app.contracts.artifacts import ArtifactRuntimeStatusResponse
from app.contracts.observability import ObservabilityGovernanceStatusResponse
from app.contracts.resilience import ResilienceGovernanceStatusResponse
from app.contracts.use_cases import (
    FirstUseCaseGovernanceStatusResponse,
    FirstUseCaseOperationalPosture,
    FirstUseCaseReadinessResponse,
    FirstUseCaseRolloutStage,
)
from app.services.first_use_case_readiness import build_first_use_case_readiness
from app.services.first_use_case_runbook_readiness import build_first_use_case_runbook_readiness
from app.services.governance_readiness import summarize_governance_flags


def build_first_use_case_governance_status(
    *,
    readiness: FirstUseCaseReadinessResponse | None = None,
    access_control_governance: AccessControlGovernanceStatusResponse | None = None,
    artifact_runtime: ArtifactRuntimeStatusResponse | None = None,
    observability_governance: ObservabilityGovernanceStatusResponse | None = None,
    resilience_governance: ResilienceGovernanceStatusResponse | None = None,
) -> FirstUseCaseGovernanceStatusResponse:
    readiness = (
        readiness
        if readiness is not None
        else build_first_use_case_readiness(
            access_control_governance=access_control_governance,
            artifact_runtime=artifact_runtime,
            observability_governance=observability_governance,
            resilience_governance=resilience_governance,
        )
    )
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
    rollout_stage = (
        FirstUseCaseRolloutStage.LIMITED_ROLLOUT
        if governance_ready
        else FirstUseCaseRolloutStage.PRE_PROD_VALIDATION
    )
    return FirstUseCaseGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        use_case_id=readiness.use_case_id,
        downstream_app=readiness.downstream_app,
        rollout_stage=rollout_stage,
        operational_posture=operational_posture,
        active_production_ready=False,
        governance_ready=governance_ready,
        readiness=readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            "The first production use case remains a bounded lotus-performance analytics-commentary path over caller-supplied structured facts rather than a broad downstream rollout.",
            (
                "Limited rollout is governance-ready because runtime evidence, durable support review, resilience governance, and runbook ownership are all in place."
                if governance_ready
                else "Limited rollout remains governance-blocked until the bounded readiness surface, including resilience governance, and the first-use-case runbook surface both report ready."
            ),
            "Active production posture remains explicitly deferred in RFC-0016; this RFC stops at a bounded limited-rollout-ready or pre-prod-validation review state.",
            (
                "Rollback posture is explicit: when first-use-case governance is no longer ready, downstream activation should be treated as blocked until the bounded contract and support signals recover."
            ),
        ],
    )
