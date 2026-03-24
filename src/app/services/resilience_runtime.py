from __future__ import annotations

from app.config import settings
from app.contracts.resilience import (
    ResilienceDeliveryStage,
    ResilienceDependencyDescriptor,
    ResilienceDependencyKind,
    ResiliencePosture,
    ResilienceRecoveryClassification,
    ResilienceRuntimeStatusResponse,
)
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.services.artifact_runtime import build_artifact_runtime_status
from app.services.async_runtime_status import build_async_runtime_status
from app.services.runtime_readiness import (
    get_access_control_store_runtime_status,
    get_artifact_store_runtime_status,
    get_async_runtime_store_runtime_status,
    get_audit_store_runtime_status,
    get_evaluation_runtime_store_runtime_status,
    get_prompt_store_runtime_status,
    get_provider_operations_store_runtime_status,
    get_retrieval_store_runtime_status,
)


def build_resilience_runtime_status() -> ResilienceRuntimeStatusResponse:
    async_runtime = build_async_runtime_status()
    artifact_runtime = build_artifact_runtime_status()
    dependencies = [
        _classify_store_dependency("audit_store", get_audit_store_runtime_status()),
        _classify_store_dependency("prompt_store", get_prompt_store_runtime_status()),
        _classify_store_dependency("retrieval_store", get_retrieval_store_runtime_status()),
        _classify_store_dependency(
            "access_control_store",
            get_access_control_store_runtime_status(),
        ),
        _classify_store_dependency(
            "provider_operations_store",
            get_provider_operations_store_runtime_status(),
        ),
        _classify_store_dependency(
            "async_runtime_store",
            get_async_runtime_store_runtime_status(),
        ),
        _classify_store_dependency(
            "evaluation_runtime_store",
            get_evaluation_runtime_store_runtime_status(),
        ),
        _classify_store_dependency("artifact_metadata_store", get_artifact_store_runtime_status()),
        _classify_async_queue_dependency(async_runtime.queue_backend),
        _classify_async_worker_dependency(async_runtime.worker_mode),
        _classify_artifact_object_dependency(
            mode=artifact_runtime.object_store_mode,
            root_configured=artifact_runtime.object_store.root_configured,
            object_store_status=artifact_runtime.object_store.status,
        ),
        _classify_live_provider_dependency(),
    ]
    authoritative_dependency_count = sum(1 for dependency in dependencies if dependency.authoritative)
    restart_survivable_dependency_count = sum(
        1 for dependency in dependencies if dependency.restart_survivable
    )
    blocking_findings = [
        dependency.detail
        for dependency in dependencies
        if dependency.recovery_classification
        in {
            ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
            ResilienceRecoveryClassification.EXTERNAL_RECOVERY_REQUIRED,
            ResilienceRecoveryClassification.BLOCKED,
        }
        and dependency.authoritative
    ]
    posture = _resolve_resilience_posture(dependencies)
    return ResilienceRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_stage=ResilienceDeliveryStage.ORDERED_RECOVERY_READY,
        posture=posture,
        dependency_count=len(dependencies),
        authoritative_dependency_count=authoritative_dependency_count,
        restart_survivable_dependency_count=restart_survivable_dependency_count,
        dependencies=dependencies,
        blocking_findings=blocking_findings,
        status_summary=[
            "Resilience runtime inventory now names the authoritative stores and critical dependencies that continuity depends on.",
            (
                "Authoritative platform truth currently remains partly local or fallback-backed, so continuity is still below a production-grade restore posture."
                if posture is ResiliencePosture.LOCAL_OR_DEMO_CONTINUITY
                else (
                    "Most authoritative platform truth is now restart-survivable, but at least one critical dependency still relies on fallback or externally managed recovery."
                    if posture is ResiliencePosture.PARTIAL_RUNTIME_DURABILITY
                    else "Authoritative stores and critical runtime dependencies are now inventoried in a prod-shaped posture, and ordered restore guidance is available even though drill evidence remains future RFC-0017 work."
                )
            ),
            "This slice now covers bounded restore ordering and validation guidance, but it still does not claim drill evidence or disaster-recovery automation.",
        ],
    )


def _resolve_resilience_posture(
    dependencies: list[ResilienceDependencyDescriptor],
) -> ResiliencePosture:
    authoritative_dependencies = [dependency for dependency in dependencies if dependency.authoritative]
    if any(
        dependency.recovery_classification is ResilienceRecoveryClassification.DOCUMENTED_FALLBACK
        and dependency.kind is ResilienceDependencyKind.AUTHORITATIVE_STORE
        for dependency in authoritative_dependencies
    ):
        return ResiliencePosture.LOCAL_OR_DEMO_CONTINUITY
    if any(
        dependency.recovery_classification
        in {
            ResilienceRecoveryClassification.EXTERNAL_RECOVERY_REQUIRED,
            ResilienceRecoveryClassification.BLOCKED,
        }
        for dependency in authoritative_dependencies
    ):
        return ResiliencePosture.PARTIAL_RUNTIME_DURABILITY
    return ResiliencePosture.INVENTORIED_PROD_SHAPED


def _classify_store_dependency(
    dependency_id: str,
    store_status: StoreRuntimeStatusDescriptor,
) -> ResilienceDependencyDescriptor:
    if store_status.mode == "memory":
        return ResilienceDependencyDescriptor(
            dependency_id=dependency_id,
            kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
            authoritative=True,
            recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
            configured_mode=store_status.mode,
            restart_survivable=False,
            detail=f"{dependency_id} is still using memory mode, so restart survival depends on local fallback behavior rather than durable recovery.",
        )
    if store_status.status is RuntimeReadinessStatus.READY:
        return ResilienceDependencyDescriptor(
            dependency_id=dependency_id,
            kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
            authoritative=True,
            recovery_classification=ResilienceRecoveryClassification.RUNTIME_RECOVERABLE,
            configured_mode=store_status.mode,
            restart_survivable=True,
            detail=f"{dependency_id} is SQL-backed and currently restart-survivable, but backup and restore ordering are not yet governed in this slice.",
        )
    if store_status.status is RuntimeReadinessStatus.MIGRATION_REQUIRED:
        return ResilienceDependencyDescriptor(
            dependency_id=dependency_id,
            kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
            authoritative=True,
            recovery_classification=ResilienceRecoveryClassification.BLOCKED,
            configured_mode=store_status.mode,
            restart_survivable=False,
            detail=f"{dependency_id} is configured for durable storage but migrations are incomplete, so continuity is blocked until schema readiness is restored.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id=dependency_id,
        kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
        authoritative=True,
        recovery_classification=ResilienceRecoveryClassification.BLOCKED,
        configured_mode=store_status.mode,
        restart_survivable=False,
        detail=f"{dependency_id} is not currently ready for durable runtime continuity: {store_status.detail}",
    )


def _classify_async_queue_dependency(queue_backend: str) -> ResilienceDependencyDescriptor:
    if queue_backend == "redis_queue":
        return ResilienceDependencyDescriptor(
            dependency_id="async_queue_backend",
            kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.RUNTIME_RECOVERABLE,
            configured_mode=queue_backend,
            restart_survivable=True,
            detail="Redis-backed queue delivery is active and can participate in runtime recovery, but broader failover rules remain future RFC-0017 work.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="async_queue_backend",
        kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
        configured_mode=queue_backend,
        restart_survivable=False,
        detail="Async queue delivery is still local, disabled, or non-managed, so worker continuity falls back to the current process-local posture.",
    )


def _classify_async_worker_dependency(worker_mode: str) -> ResilienceDependencyDescriptor:
    if worker_mode == "DEDICATED":
        return ResilienceDependencyDescriptor(
            dependency_id="async_worker_mode",
            kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.RUNTIME_RECOVERABLE,
            configured_mode=worker_mode,
            restart_survivable=True,
            detail="Dedicated workers are active for allowlisted async execution and inherit runtime-backed job recovery semantics.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="async_worker_mode",
        kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
        configured_mode=worker_mode,
        restart_survivable=False,
        detail="Async execution still depends on unified or non-primary worker posture, so recovery remains local or narrowly documented.",
    )


def _classify_artifact_object_dependency(
    *,
    mode: str,
    root_configured: bool,
    object_store_status: RuntimeReadinessStatus,
) -> ResilienceDependencyDescriptor:
    if object_store_status is RuntimeReadinessStatus.CONFIGURATION_REQUIRED:
        return ResilienceDependencyDescriptor(
            dependency_id="artifact_object_store",
            kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
            authoritative=True,
            recovery_classification=ResilienceRecoveryClassification.BLOCKED,
            configured_mode=mode,
            restart_survivable=False,
            detail="Artifact payload storage is configured but missing required object-store root settings, so payload recovery posture is blocked.",
        )
    if mode in {"memory", "filesystem"}:
        return ResilienceDependencyDescriptor(
            dependency_id="artifact_object_store",
            kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
            authoritative=True,
            recovery_classification=ResilienceRecoveryClassification.EXTERNAL_RECOVERY_REQUIRED,
            configured_mode=mode,
            restart_survivable=(mode == "filesystem" and root_configured),
            detail="Artifact payload storage still relies on local fallback storage, so resilience depends on external filesystem handling rather than governed object-store recovery.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="artifact_object_store",
        kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
        authoritative=True,
        recovery_classification=ResilienceRecoveryClassification.BLOCKED,
        configured_mode=mode,
        restart_survivable=False,
        detail="Artifact payload storage is not yet configured through a recognized production object-store backend.",
    )


def _classify_live_provider_dependency() -> ResilienceDependencyDescriptor:
    if settings.provider_mode == "openai":
        return ResilienceDependencyDescriptor(
            dependency_id="live_provider_dependency",
            kind=ResilienceDependencyKind.EXTERNAL_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.EXTERNAL_RECOVERY_REQUIRED,
            configured_mode=settings.provider_mode,
            restart_survivable=False,
            detail="Live provider execution depends on external upstream recovery and should not be treated as internally restorable platform state.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="live_provider_dependency",
        kind=ResilienceDependencyKind.EXTERNAL_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
        configured_mode=settings.provider_mode,
        restart_survivable=False,
        detail="Live provider execution is not currently active, so external-provider resilience remains a documented future dependency rather than an active continuity path.",
    )
