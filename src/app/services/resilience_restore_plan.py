from __future__ import annotations

from app.config import settings
from app.contracts.resilience import (
    ResilienceDeliveryStage,
    ResilienceRestoreClassification,
    ResilienceRestorePlanResponse,
    ResilienceRestoreStepDescriptor,
)


def build_resilience_restore_plan() -> ResilienceRestorePlanResponse:
    restore_steps = [
        ResilienceRestoreStepDescriptor(
            step_id="restore_authoritative_relational_metadata",
            sequence=1,
            classification=ResilienceRestoreClassification.PLATFORM_METADATA_RESTORE,
            dependency_ids=[
                "audit_store",
                "prompt_store",
                "retrieval_store",
                "access_control_store",
                "provider_operations_store",
                "async_runtime_store",
                "evaluation_runtime_store",
                "artifact_metadata_store",
            ],
            requires_completed_steps=[],
            restore_action_summary=(
                "Restore the authoritative relational stores first so audit, caller policy, prompt rollout, "
                "retrieval metadata, provider operations, async runtime, evaluation runtime, and artifact metadata "
                "all re-establish one coherent platform truth before downstream runtime reconciliation begins."
            ),
            success_criteria=[
                "All authoritative relational stores report durable READY posture through their runtime-readiness surfaces.",
                "Schema migrations are fully applied before any runtime reconciliation step proceeds.",
                "Platform runtime status no longer reports blocked relational continuity findings for the restored stores.",
            ],
            rollback_boundary=(
                "This step restores durable metadata only. It does not re-enable rollout, replay workers, or change "
                "application behavior on its own."
            ),
        ),
        ResilienceRestoreStepDescriptor(
            step_id="reconcile_artifact_payload_storage",
            sequence=2,
            classification=ResilienceRestoreClassification.PLATFORM_METADATA_RESTORE,
            dependency_ids=["artifact_object_store"],
            requires_completed_steps=["restore_authoritative_relational_metadata"],
            restore_action_summary=(
                "Reconcile artifact payload storage against restored artifact metadata so governed payload descriptors "
                "can be trusted again before incident review or runtime evidence inspection resumes."
            ),
            success_criteria=[
                "Artifact object-store root or backend is reachable and no longer reports configuration-required posture.",
                "Artifact metadata descriptors can be matched to a configured payload backend without raw path guessing.",
                "Operators can inspect artifact runtime status without blocked payload-store findings.",
            ],
            rollback_boundary=(
                "This step restores payload availability for governed evidence. It does not archive, delete, or "
                "supersede artifacts as part of recovery."
            ),
        ),
        ResilienceRestoreStepDescriptor(
            step_id="reconcile_runtime_delivery_state",
            sequence=3,
            classification=ResilienceRestoreClassification.PLATFORM_RUNTIME_RECONCILIATION,
            dependency_ids=["async_queue_backend", "async_worker_mode"],
            requires_completed_steps=[
                "restore_authoritative_relational_metadata",
                "reconcile_artifact_payload_storage",
            ],
            restore_action_summary=(
                "Bring queue-backed delivery and workers back into a coherent state only after durable runtime records "
                "exist again, so lease recovery, replay, retry, and evaluation attempt linkage continue from restored truth."
            ),
            success_criteria=[
                "Async runtime status shows the expected queue backend and worker mode without fallback-only posture.",
                "Queued or claimed jobs can be explained through runtime-backed async job state rather than process-local inference.",
                "Evaluation runtime remains linked to async recovery semantics instead of diverging into a separate restore path.",
            ],
            rollback_boundary=(
                "This step reconciles execution flow. It does not approve broader activation or treat recovery as proof "
                "that the platform is healthy for downstream rollout."
            ),
        ),
        ResilienceRestoreStepDescriptor(
            step_id="validate_external_dependencies",
            sequence=4,
            classification=ResilienceRestoreClassification.EXTERNAL_DEPENDENCY_VALIDATION,
            dependency_ids=["live_provider_dependency"],
            requires_completed_steps=["reconcile_runtime_delivery_state"],
            restore_action_summary=(
                "Validate external provider posture after internal state is coherent so upstream availability is "
                "reviewed explicitly instead of being mistaken for internally restored platform truth."
            ),
            success_criteria=[
                "Provider governance and operations status can explain whether live execution remains disabled, degraded, or active.",
                "External upstream recovery is reviewed separately from internal store restore completion.",
                "Downstream use-case rollout remains blocked if provider governance or first-use-case governance is still not ready.",
            ],
            rollback_boundary=(
                "This step validates external readiness only. It does not silently re-enable live provider rollout or "
                "override bounded caller-policy controls."
            ),
        ),
    ]
    return ResilienceRestorePlanResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_stage=ResilienceDeliveryStage.DRILL_VERIFIED,
        restore_step_count=len(restore_steps),
        restore_steps=restore_steps,
        restore_validation_summary=[
            "Restore authoritative relational metadata before queue, worker, or artifact payload reconciliation begins.",
            "Treat rollback of application behavior as distinct from restore of durable state throughout the plan.",
            "Use detailed runtime and governance surfaces to validate each step instead of assuming a process restart completed recovery.",
        ],
        status_summary=[
            "RFC-0017 now defines an ordered restore plan for authoritative stores and critical dependencies.",
            "This slice keeps restore ordering bounded and explicit while adding separate drill-evidence and governance review surfaces.",
        ],
    )
