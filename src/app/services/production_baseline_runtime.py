from __future__ import annotations

from types import SimpleNamespace

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselineDependencyDescriptor,
    ProductionBaselinePosture,
    ProductionBaselineRuntimeStatusResponse,
    ProductionDependencyClassification,
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


def build_production_baseline_runtime_status(
    app_state: object | None = None,
) -> ProductionBaselineRuntimeStatusResponse:
    startup_state = _resolve_startup_readiness_state(app_state)
    async_runtime = build_async_runtime_status()
    artifact_runtime = build_artifact_runtime_status()

    dependencies = [
        _classify_database_backend(),
        _classify_sql_store_group(
            "durable_sql_state",
            [
                get_audit_store_runtime_status(),
                get_prompt_store_runtime_status(),
                get_retrieval_store_runtime_status(),
                get_access_control_store_runtime_status(),
                get_provider_operations_store_runtime_status(),
                get_async_runtime_store_runtime_status(),
                get_evaluation_runtime_store_runtime_status(),
                get_artifact_store_runtime_status(),
            ],
        ),
        _classify_async_queue(async_runtime.queue_backend),
        _classify_async_worker(async_runtime.worker_mode),
        _classify_artifact_object_store(artifact_runtime.object_store_mode),
        _classify_secret_posture(),
        _classify_migration_posture(startup_state.warnings),
        _classify_live_provider_rollout(),
    ]

    blocked_dependency_count = sum(
        1
        for dependency in dependencies
        if dependency.production_required
        and dependency.classification is ProductionDependencyClassification.BLOCKED
    )
    fallback_dependency_count = sum(
        1
        for dependency in dependencies
        if dependency.classification is ProductionDependencyClassification.FALLBACK
    )
    production_ready = (
        blocked_dependency_count == 0
        and fallback_dependency_count == 0
        and not startup_state.blocking
    )
    prod_shaped_local = _is_prod_shaped_local(dependencies)
    posture = _resolve_posture(
        production_ready=production_ready,
        prod_shaped_local=prod_shaped_local,
    )

    blocking_findings = [
        dependency.detail
        for dependency in dependencies
        if dependency.production_required
        and dependency.classification is not ProductionDependencyClassification.PRODUCTION_STANDARD
    ]
    if startup_state.blocking:
        blocking_findings.extend(startup_state.warnings)

    status_summary = [
        (
            "Lotus-ai currently satisfies the RFC-0020 production baseline."
            if production_ready
            else "Lotus-ai is not yet at the RFC-0020 production baseline."
        ),
        (
            "The current posture is prod-shaped local: containerized API, worker, and queue topology are active, but at least one required production dependency still remains fallback or blocked."
            if prod_shaped_local and not production_ready
            else "The current posture remains local or demo-capable rather than a prod-shaped local deployment."
        ),
        (
            "Live-provider success does not by itself imply production readiness; store, secret, artifact, migration, and governance posture still decide whether the baseline is production-standard."
        ),
    ]

    return ProductionBaselineRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        posture=posture,
        prod_shaped_local=prod_shaped_local,
        production_ready=production_ready,
        dependency_count=len(dependencies),
        blocked_dependency_count=blocked_dependency_count,
        fallback_dependency_count=fallback_dependency_count,
        dependencies=dependencies,
        blocking_findings=blocking_findings,
        status_summary=status_summary,
    )


def _resolve_startup_readiness_state(app_state: object | None) -> SimpleNamespace:
    state = app_state if app_state is not None else SimpleNamespace()
    return SimpleNamespace(
        blocking=bool(getattr(state, "startup_readiness_blocking", False)),
        warnings=list(getattr(state, "startup_readiness_findings", [])),
    )


def _is_prod_shaped_local(
    dependencies: list[ProductionBaselineDependencyDescriptor],
) -> bool:
    required_ids = {"async_queue_backend", "async_worker_mode"}
    dependency_by_id = {dependency.dependency_id: dependency for dependency in dependencies}
    return all(
        dependency_by_id[dependency_id].classification
        is ProductionDependencyClassification.PRODUCTION_STANDARD
        for dependency_id in required_ids
    )


def _resolve_posture(
    *, production_ready: bool, prod_shaped_local: bool
) -> ProductionBaselinePosture:
    if production_ready:
        return ProductionBaselinePosture.PRODUCTION_READY
    if prod_shaped_local:
        return ProductionBaselinePosture.PROD_SHAPED_LOCAL
    return ProductionBaselinePosture.LOCAL_OR_DEMO_CAPABLE


def _classify_database_backend() -> ProductionBaselineDependencyDescriptor:
    database_url = settings.database_url or ""
    if database_url.startswith("postgresql://") or database_url.startswith("postgresql+"):
        return ProductionBaselineDependencyDescriptor(
            dependency_id="database_backend",
            classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
            production_required=True,
            configured_mode="postgresql",
            detail="PostgreSQL is configured as the authoritative relational backend.",
        )
    if database_url.startswith("sqlite:"):
        return ProductionBaselineDependencyDescriptor(
            dependency_id="database_backend",
            classification=ProductionDependencyClassification.FALLBACK,
            production_required=True,
            configured_mode="sqlite",
            detail="SQLite is configured as the relational backend, which is acceptable for local or demo posture but not for the RFC-0020 production baseline.",
        )
    if database_url:
        return ProductionBaselineDependencyDescriptor(
            dependency_id="database_backend",
            classification=ProductionDependencyClassification.BLOCKED,
            production_required=True,
            configured_mode="other",
            detail="A non-standard relational backend is configured and is not yet recognized as a production-standard RFC-0020 posture.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="database_backend",
        classification=ProductionDependencyClassification.BLOCKED,
        production_required=True,
        configured_mode="unconfigured",
        detail="No relational database backend is configured for the production baseline.",
    )


def _classify_sql_store_group(
    dependency_id: str, stores: list[StoreRuntimeStatusDescriptor]
) -> ProductionBaselineDependencyDescriptor:
    if any(store.mode == "memory" for store in stores):
        return ProductionBaselineDependencyDescriptor(
            dependency_id=dependency_id,
            classification=ProductionDependencyClassification.FALLBACK,
            production_required=True,
            configured_mode="mixed_or_memory",
            detail="At least one durable control-plane or runtime store is still running in memory mode, so the service remains below the production baseline.",
        )
    if any(store.status is not RuntimeReadinessStatus.READY for store in stores):
        return ProductionBaselineDependencyDescriptor(
            dependency_id=dependency_id,
            classification=ProductionDependencyClassification.BLOCKED,
            production_required=True,
            configured_mode="sqlalchemy",
            detail="At least one required SQL-backed runtime store is not ready, so the durable-state production baseline is blocked.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id=dependency_id,
        classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
        production_required=True,
        configured_mode="sqlalchemy",
        detail="All required durable runtime and control-plane stores are configured through the SQL-backed seams and are currently ready.",
    )


def _classify_async_queue(queue_backend: str) -> ProductionBaselineDependencyDescriptor:
    if queue_backend == "redis_queue":
        return ProductionBaselineDependencyDescriptor(
            dependency_id="async_queue_backend",
            classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
            production_required=True,
            configured_mode=queue_backend,
            detail="Redis-backed queue delivery is active for the dedicated worker path.",
        )
    if queue_backend in {"none", "memory"}:
        return ProductionBaselineDependencyDescriptor(
            dependency_id="async_queue_backend",
            classification=ProductionDependencyClassification.FALLBACK,
            production_required=True,
            configured_mode=queue_backend,
            detail="Queue delivery is not using the managed Redis backend, so the service remains in local or demo posture.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="async_queue_backend",
        classification=ProductionDependencyClassification.BLOCKED,
        production_required=True,
        configured_mode=queue_backend,
        detail="The configured async queue backend is not recognized as a production-standard RFC-0020 posture.",
    )


def _classify_async_worker(worker_mode: str) -> ProductionBaselineDependencyDescriptor:
    if worker_mode == "DEDICATED":
        return ProductionBaselineDependencyDescriptor(
            dependency_id="async_worker_mode",
            classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
            production_required=True,
            configured_mode=worker_mode,
            detail="Dedicated worker execution is active for allowlisted async job types.",
        )
    if worker_mode in {"IN_PROCESS_ONLY", "SHADOW_ONLY"}:
        return ProductionBaselineDependencyDescriptor(
            dependency_id="async_worker_mode",
            classification=ProductionDependencyClassification.FALLBACK,
            production_required=True,
            configured_mode=worker_mode,
            detail="Async execution is still relying on a local or non-primary worker posture rather than the dedicated production path.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="async_worker_mode",
        classification=ProductionDependencyClassification.BLOCKED,
        production_required=True,
        configured_mode=worker_mode,
        detail="The configured async worker posture is degraded or unsupported for the production baseline.",
    )


def _classify_artifact_object_store(
    object_store_mode: str,
) -> ProductionBaselineDependencyDescriptor:
    if object_store_mode in {"memory", "filesystem"}:
        return ProductionBaselineDependencyDescriptor(
            dependency_id="artifact_object_store",
            classification=ProductionDependencyClassification.FALLBACK,
            production_required=True,
            configured_mode=object_store_mode,
            detail="Artifact payload storage is still using a local fallback backend rather than a governed production object store.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="artifact_object_store",
        classification=ProductionDependencyClassification.BLOCKED,
        production_required=True,
        configured_mode=object_store_mode,
        detail="Artifact payload storage is not yet configured through a recognized production-standard object-store backend.",
    )


def _classify_secret_posture() -> ProductionBaselineDependencyDescriptor:
    if settings.secret_source_mode == "deployment_managed":
        return ProductionBaselineDependencyDescriptor(
            dependency_id="secret_posture",
            classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
            production_required=True,
            configured_mode=settings.secret_source_mode,
            detail="Runtime secrets are declared as deployment-managed rather than local project-file driven.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="secret_posture",
        classification=ProductionDependencyClassification.FALLBACK,
        production_required=True,
        configured_mode=settings.secret_source_mode,
        detail="Secret posture is still local or unspecified, which is acceptable for demos but not for the RFC-0020 production baseline.",
    )


def _classify_migration_posture(
    startup_warnings: list[str],
) -> ProductionBaselineDependencyDescriptor:
    if any("migration required" in warning.lower() for warning in startup_warnings):
        return ProductionBaselineDependencyDescriptor(
            dependency_id="migration_posture",
            classification=ProductionDependencyClassification.BLOCKED,
            production_required=True,
            configured_mode="schema_not_ready",
            detail="Startup readiness reported a migration-related finding, so the production baseline remains blocked.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="migration_posture",
        classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
        production_required=True,
        configured_mode="schema_ready",
        detail="Startup readiness does not currently report migration blockers for the configured runtime stores.",
    )


def _classify_live_provider_rollout() -> ProductionBaselineDependencyDescriptor:
    if settings.provider_mode != "openai":
        return ProductionBaselineDependencyDescriptor(
            dependency_id="live_provider_rollout",
            classification=ProductionDependencyClassification.FALLBACK,
            production_required=False,
            configured_mode=settings.provider_mode,
            detail="Live provider execution is not active in the current runtime posture.",
        )
    if settings.provider_rollout_state in {"CANARY_ENABLED", "ROLLED_OUT"}:
        return ProductionBaselineDependencyDescriptor(
            dependency_id="live_provider_rollout",
            classification=ProductionDependencyClassification.PRODUCTION_STANDARD,
            production_required=False,
            configured_mode=settings.provider_rollout_state,
            detail="Live provider execution is configured in an explicit rollout posture rather than remaining stub-default only.",
        )
    return ProductionBaselineDependencyDescriptor(
        dependency_id="live_provider_rollout",
        classification=ProductionDependencyClassification.FALLBACK,
        production_required=False,
        configured_mode=settings.provider_rollout_state,
        detail="Live provider execution remains outside an activatable rollout posture.",
    )
