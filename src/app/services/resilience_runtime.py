from __future__ import annotations

from app.config import settings
from app.contracts.resilience import (
    ResilienceDeliveryStage,
    ResilienceDependencyDescriptor,
    ResilienceDependencyKind,
    ResilienceRecoveryState,
    ResiliencePosture,
    ResilienceRecoveryClassification,
    ResilienceRuntimeStatusResponse,
)
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.services.artifact_runtime import build_artifact_runtime_status
from app.services.async_runtime_status import build_async_runtime_status
from app.services.provider_operations_status import build_provider_operations_status
from app.services.retrieval_execution_status import build_retrieval_execution_status
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
    provider_operations = build_provider_operations_status()
    retrieval_execution = build_retrieval_execution_status()
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
        _classify_async_queue_dependency(
            queue_backend=async_runtime.queue_backend,
            degraded_findings=async_runtime.degraded_findings,
        ),
        _classify_async_worker_dependency(
            worker_mode=async_runtime.worker_mode,
            degraded_findings=async_runtime.degraded_findings,
        ),
        _classify_artifact_object_dependency(
            mode=artifact_runtime.object_store_mode,
            root_configured=artifact_runtime.object_store.root_configured,
            object_store_status=artifact_runtime.object_store.status,
        ),
        _classify_retrieval_dependency(
            retrieval_mode=retrieval_execution.retrieval_mode,
            execution_stage=retrieval_execution.execution_stage.value,
            split_route_degraded=retrieval_execution.split_route_degraded,
            findings=[*retrieval_execution.split_route_findings],
            message=retrieval_execution.message,
        ),
        _classify_live_provider_dependency(
            provider_mode=settings.provider_mode,
            operations_state=provider_operations.operations_state.value,
            runtime_execution_enabled=provider_operations.runtime_execution_enabled,
            findings=provider_operations.blocking_reasons,
        ),
    ]
    authoritative_dependency_count = sum(1 for dependency in dependencies if dependency.authoritative)
    restart_survivable_dependency_count = sum(
        1 for dependency in dependencies if dependency.restart_survivable
    )
    recovery_findings = [
        f"{dependency.dependency_id}: {dependency.recovery_findings[0]}"
        for dependency in dependencies
        if dependency.recovery_state is not ResilienceRecoveryState.STEADY
        and dependency.recovery_findings
    ]
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
    recovery_state = _resolve_recovery_state(dependencies)
    return ResilienceRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_stage=ResilienceDeliveryStage.ORDERED_RECOVERY_READY,
        recovery_state=recovery_state,
        posture=posture,
        dependency_count=len(dependencies),
        authoritative_dependency_count=authoritative_dependency_count,
        restart_survivable_dependency_count=restart_survivable_dependency_count,
        dependencies=dependencies,
        recovery_attention_dependency_count=len(recovery_findings),
        recovery_findings=recovery_findings,
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
            (
                "Current runtime recovery posture is steady across the critical continuity dependencies."
                if recovery_state is ResilienceRecoveryState.STEADY
                else (
                    "At least one critical continuity dependency is currently degraded and should not be treated as restored."
                    if recovery_state is ResilienceRecoveryState.DEGRADED
                    else "Critical continuity dependencies are running again, but at least one dependency still carries restored-with-findings posture that requires operator review."
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


def _resolve_recovery_state(
    dependencies: list[ResilienceDependencyDescriptor],
) -> ResilienceRecoveryState:
    if any(
        dependency.recovery_state is ResilienceRecoveryState.DEGRADED
        for dependency in dependencies
    ):
        return ResilienceRecoveryState.DEGRADED
    if any(
        dependency.recovery_state is ResilienceRecoveryState.RESTORED_WITH_FINDINGS
        for dependency in dependencies
    ):
        return ResilienceRecoveryState.RESTORED_WITH_FINDINGS
    return ResilienceRecoveryState.STEADY


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
            recovery_state=ResilienceRecoveryState.DEGRADED,
            recovery_findings=[
                f"{dependency_id} still depends on memory-backed fallback, so runtime continuity remains degraded under restart or recovery review."
            ],
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
            recovery_state=ResilienceRecoveryState.STEADY,
            recovery_findings=[],
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
            recovery_state=ResilienceRecoveryState.DEGRADED,
            recovery_findings=[
                "Migrations are incomplete, so this authoritative store cannot be treated as restored."
            ],
            detail=f"{dependency_id} is configured for durable storage but migrations are incomplete, so continuity is blocked until schema readiness is restored.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id=dependency_id,
        kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
        authoritative=True,
        recovery_classification=ResilienceRecoveryClassification.BLOCKED,
        configured_mode=store_status.mode,
        restart_survivable=False,
        recovery_state=ResilienceRecoveryState.DEGRADED,
        recovery_findings=[store_status.detail],
        detail=f"{dependency_id} is not currently ready for durable runtime continuity: {store_status.detail}",
    )


def _classify_async_queue_dependency(
    *,
    queue_backend: str,
    degraded_findings: list[str],
) -> ResilienceDependencyDescriptor:
    if queue_backend == "redis_queue":
        queue_findings = [
            finding for finding in degraded_findings if "queue" in finding.lower()
        ]
        return ResilienceDependencyDescriptor(
            dependency_id="async_queue_backend",
            kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.RUNTIME_RECOVERABLE,
            configured_mode=queue_backend,
            restart_survivable=True,
            recovery_state=(
                ResilienceRecoveryState.DEGRADED
                if queue_findings
                else ResilienceRecoveryState.STEADY
            ),
            recovery_findings=queue_findings,
            detail="Redis-backed queue delivery is active and can participate in runtime recovery, but broader failover rules remain future RFC-0017 work.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="async_queue_backend",
        kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
        configured_mode=queue_backend,
        restart_survivable=False,
        recovery_state=ResilienceRecoveryState.DEGRADED,
        recovery_findings=[
            "Queue delivery is not running on the managed backend, so async recovery remains on a fallback posture."
        ],
        detail="Async queue delivery is still local, disabled, or non-managed, so worker continuity falls back to the current process-local posture.",
    )


def _classify_async_worker_dependency(
    *,
    worker_mode: str,
    degraded_findings: list[str],
) -> ResilienceDependencyDescriptor:
    if worker_mode == "DEDICATED":
        worker_findings = list(degraded_findings)
        return ResilienceDependencyDescriptor(
            dependency_id="async_worker_mode",
            kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.RUNTIME_RECOVERABLE,
            configured_mode=worker_mode,
            restart_survivable=True,
            recovery_state=(
                ResilienceRecoveryState.DEGRADED
                if worker_findings
                else ResilienceRecoveryState.STEADY
            ),
            recovery_findings=worker_findings,
            detail="Dedicated workers are active for allowlisted async execution and inherit runtime-backed job recovery semantics.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="async_worker_mode",
        kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
        configured_mode=worker_mode,
        restart_survivable=False,
        recovery_state=ResilienceRecoveryState.DEGRADED,
        recovery_findings=[
            "Dedicated worker recovery is not active, so async execution is still operating in a fallback or local posture."
        ],
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
            recovery_state=ResilienceRecoveryState.DEGRADED,
            recovery_findings=[
                "Artifact payload storage is configured but missing the backing root, so artifact-backed incident review is not restored."
            ],
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
            recovery_state=(
                ResilienceRecoveryState.RESTORED_WITH_FINDINGS
                if mode == "filesystem" and root_configured
                else ResilienceRecoveryState.DEGRADED
            ),
            recovery_findings=[
                (
                    "Artifact payloads are available again through the configured filesystem seam, but operators still need external filesystem handling to treat payload recovery as durable."
                    if mode == "filesystem" and root_configured
                    else "Artifact payload storage remains on in-memory fallback, so payload recovery is degraded."
                )
            ],
            detail="Artifact payload storage still relies on local fallback storage, so resilience depends on external filesystem handling rather than governed object-store recovery.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="artifact_object_store",
        kind=ResilienceDependencyKind.AUTHORITATIVE_STORE,
        authoritative=True,
        recovery_classification=ResilienceRecoveryClassification.BLOCKED,
        configured_mode=mode,
        restart_survivable=False,
        recovery_state=ResilienceRecoveryState.DEGRADED,
        recovery_findings=[
            "Artifact payload storage is not configured through a recognized backend, so payload recovery remains blocked."
        ],
        detail="Artifact payload storage is not yet configured through a recognized production object-store backend.",
    )


def _classify_retrieval_dependency(
    *,
    retrieval_mode: str,
    execution_stage: str,
    split_route_degraded: bool,
    findings: list[str],
    message: str,
) -> ResilienceDependencyDescriptor:
    if retrieval_mode != "enabled":
        return ResilienceDependencyDescriptor(
            dependency_id="retrieval_execution_path",
            kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
            configured_mode=retrieval_mode,
            restart_survivable=False,
            recovery_state=ResilienceRecoveryState.STEADY,
            recovery_findings=[],
            detail="Retrieval live execution is not currently active, so retrieval recovery remains a documented future dependency rather than an active runtime continuity path.",
        )
    degraded = split_route_degraded or execution_stage != "LIVE_SEARCH"
    recovery_findings = [*findings]
    if degraded and not recovery_findings:
        recovery_findings = [message]
    return ResilienceDependencyDescriptor(
        dependency_id="retrieval_execution_path",
        kind=ResilienceDependencyKind.RUNTIME_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.RUNTIME_RECOVERABLE,
        configured_mode=retrieval_mode,
        restart_survivable=True,
        recovery_state=(
            ResilienceRecoveryState.DEGRADED if degraded else ResilienceRecoveryState.STEADY
        ),
        recovery_findings=recovery_findings,
        detail="Retrieval execution recovery is derived from the live execution stage and split-route posture rather than from process restart alone.",
    )


def _classify_live_provider_dependency(
    *,
    provider_mode: str,
    operations_state: str,
    runtime_execution_enabled: bool,
    findings: list[str],
) -> ResilienceDependencyDescriptor:
    if provider_mode == "openai":
        return ResilienceDependencyDescriptor(
            dependency_id="live_provider_dependency",
            kind=ResilienceDependencyKind.EXTERNAL_DEPENDENCY,
            authoritative=False,
            recovery_classification=ResilienceRecoveryClassification.EXTERNAL_RECOVERY_REQUIRED,
            configured_mode=provider_mode,
            restart_survivable=False,
            recovery_state=(
                ResilienceRecoveryState.DEGRADED
                if operations_state != "NORMAL"
                else ResilienceRecoveryState.STEADY
            ),
            recovery_findings=(
                list(findings)
                if operations_state != "NORMAL"
                else []
            ),
            detail="Live provider execution depends on external upstream recovery and should not be treated as internally restorable platform state.",
        )
    return ResilienceDependencyDescriptor(
        dependency_id="live_provider_dependency",
        kind=ResilienceDependencyKind.EXTERNAL_DEPENDENCY,
        authoritative=False,
        recovery_classification=ResilienceRecoveryClassification.DOCUMENTED_FALLBACK,
        configured_mode=provider_mode,
        restart_survivable=False,
        recovery_state=(
            ResilienceRecoveryState.STEADY
            if not runtime_execution_enabled
            else ResilienceRecoveryState.DEGRADED
        ),
        recovery_findings=[],
        detail="Live provider execution is not currently active, so external-provider resilience remains a documented future dependency rather than an active continuity path.",
    )
