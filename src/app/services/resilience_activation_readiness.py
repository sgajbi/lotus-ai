from __future__ import annotations

from app.config import settings
from app.contracts.resilience import (
    ResilienceActivationReadinessResponse,
    ResilienceDeliveryStage,
    ResiliencePosture,
    ResilienceRecoveryState,
)
from app.services.resilience_drill_evidence import build_resilience_drill_evidence
from app.services.resilience_restore_plan import build_resilience_restore_plan
from app.services.resilience_runtime import build_resilience_runtime_status


def build_resilience_activation_readiness() -> ResilienceActivationReadinessResponse:
    runtime_status = build_resilience_runtime_status()
    restore_plan = build_resilience_restore_plan()
    drill_evidence = build_resilience_drill_evidence()

    blocking_findings = list(runtime_status.blocking_findings)
    if runtime_status.posture is ResiliencePosture.LOCAL_OR_DEMO_CONTINUITY:
        blocking_findings.append(
            "Resilience activation remains blocked while authoritative continuity still depends on local or demo fallback posture."
        )
    if runtime_status.recovery_state is ResilienceRecoveryState.DEGRADED:
        blocking_findings.append(
            "Resilience activation remains blocked while one or more critical continuity dependencies are still degraded rather than restored."
        )
    if restore_plan.restore_step_count == 0:
        blocking_findings.append(
            "Resilience activation requires an ordered restore plan before governance can treat recovery posture as active."
        )
    if not drill_evidence.drill_evidence_ready:
        blocking_findings.append(
            "Resilience activation remains blocked until required drill and recovery-proof evidence is marked ready."
        )

    return ResilienceActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_stage=ResilienceDeliveryStage.DRILL_VERIFIED,
        recovery_state=runtime_status.recovery_state,
        activation_ready=not blocking_findings,
        blocking_findings=blocking_findings,
        activation_path=[
            "Inspect `/platform/resilience/runtime-status` to confirm critical continuity dependencies are no longer degraded.",
            "Inspect `/platform/resilience/restore-plan` to confirm restore ordering and rollback boundaries remain explicit.",
            "Inspect `/platform/resilience/drill-evidence` to verify required recovery-proof evidence is current rather than staged-only.",
            "Treat resilience governance as ready only when `/platform/resilience/governance-status` and the embedded `resilience_governance` block in `/platform/runtime-status` agree.",
        ],
    )
