from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.services.production_baseline_runtime import (
    _resolve_posture,
    build_production_baseline_runtime_status,
)


def test_production_baseline_runtime_defaults_to_local_or_demo_capable() -> None:
    settings.database_url = None
    settings.audit_store_mode = "memory"
    settings.prompt_store_mode = "memory"
    settings.retrieval_store_mode = "memory"
    settings.access_control_store_mode = "memory"
    settings.provider_operations_store_mode = "memory"
    settings.async_runtime_store_mode = "memory"
    settings.evaluation_runtime_store_mode = "memory"
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.secret_source_mode = "local_or_unspecified"
    settings.provider_mode = "disabled"
    settings.provider_rollout_state = "STUB_DEFAULT"
    settings.async_cutover_state = "in_process_only"
    settings.async_queue_backend_mode = "none"
    settings.async_queue_redis_url = None
    status = build_production_baseline_runtime_status(None)

    assert status.posture.value == "LOCAL_OR_DEMO_CAPABLE"
    assert status.prod_shaped_local is False
    assert status.production_ready is False
    assert status.blocked_dependency_count >= 1
    assert any(
        dependency.dependency_id == "database_backend"
        and dependency.classification.value == "BLOCKED"
        for dependency in status.dependencies
    )


def test_production_baseline_runtime_reports_prod_shaped_local_but_not_production_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = "/data/object-store"
    settings.secret_source_mode = "local_or_unspecified"
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_audit_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_prompt_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_retrieval_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_access_control_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_provider_operations_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_async_runtime_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_evaluation_runtime_store_runtime_status",
        lambda: ready_store,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_artifact_store_runtime_status",
        lambda: ready_store,
    )

    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="redis_queue", worker_mode="DEDICATED"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="filesystem",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.READY,
                root_configured=True,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(startup_readiness_blocking=False, startup_readiness_findings=[])
    )

    assert status.posture.value == "PROD_SHAPED_LOCAL"
    assert status.prod_shaped_local is True
    assert status.production_ready is False
    assert any(
        dependency.dependency_id == "database_backend"
        and dependency.classification.value == "PRODUCTION_STANDARD"
        for dependency in status.dependencies
    )
    assert any(
        dependency.dependency_id == "artifact_object_store"
        and dependency.classification.value == "FALLBACK"
        for dependency in status.dependencies
    )
    assert any(
        dependency.dependency_id == "secret_posture"
        and dependency.classification.value == "FALLBACK"
        for dependency in status.dependencies
    )


def test_production_baseline_runtime_does_not_treat_sqlite_as_prod_shaped_local(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "sqlite:///./lotus-ai.db"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = "/data/object-store"
    settings.secret_source_mode = "local_or_unspecified"
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    for target in (
        "get_audit_store_runtime_status",
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )

    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="redis_queue", worker_mode="DEDICATED"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="filesystem",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.READY,
                root_configured=True,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(startup_readiness_blocking=False, startup_readiness_findings=[])
    )

    assert status.posture.value == "LOCAL_OR_DEMO_CAPABLE"
    assert status.prod_shaped_local is False
    assert any(
        dependency.dependency_id == "database_backend"
        and dependency.classification.value == "FALLBACK"
        for dependency in status.dependencies
    )


def test_production_baseline_runtime_blocks_missing_artifact_root_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = None
    settings.secret_source_mode = "deployment_managed"
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    for target in (
        "get_audit_store_runtime_status",
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )

    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="redis_queue", worker_mode="DEDICATED"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="filesystem",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.CONFIGURATION_REQUIRED,
                root_configured=False,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(startup_readiness_blocking=False, startup_readiness_findings=[])
    )

    assert status.posture.value == "PROD_SHAPED_LOCAL"
    assert status.production_ready is False
    assert any(
        dependency.dependency_id == "artifact_object_store"
        and dependency.classification.value == "BLOCKED"
        for dependency in status.dependencies
    )


def test_production_baseline_runtime_names_non_ready_sql_store_group_dependency(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = "/data/object-store"
    settings.secret_source_mode = "deployment_managed"
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    migration_required_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.MIGRATION_REQUIRED,
        database_configured=True,
        detail="missing tables",
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_audit_store_runtime_status",
        lambda: migration_required_store,
    )
    for target in (
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="redis_queue", worker_mode="DEDICATED"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="filesystem",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.READY,
                root_configured=True,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(startup_readiness_blocking=False, startup_readiness_findings=[])
    )

    durable_state_dependency = next(
        dependency
        for dependency in status.dependencies
        if dependency.dependency_id == "durable_sql_state"
    )
    assert durable_state_dependency.classification.value == "BLOCKED"
    assert "audit" in durable_state_dependency.detail


def test_resolve_posture_prefers_production_ready_over_prod_shaped_local() -> None:
    posture = _resolve_posture(production_ready=True, prod_shaped_local=True)

    assert posture.value == "PRODUCTION_READY"


def test_production_baseline_runtime_blocks_unrecognized_database_backend() -> None:
    settings.database_url = "mysql://lotus:lotus@db:3306/lotus_ai"

    status = build_production_baseline_runtime_status(None)

    dependency = next(
        item for item in status.dependencies if item.dependency_id == "database_backend"
    )
    assert dependency.classification.value == "BLOCKED"
    assert dependency.configured_mode == "other"


def test_production_baseline_runtime_blocks_unsupported_sql_store_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    settings.audit_store_mode = "custom"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = "/data/object-store"
    settings.secret_source_mode = "deployment_managed"
    unsupported_store = StoreRuntimeStatusDescriptor(
        mode="custom",
        status=RuntimeReadinessStatus.UNAVAILABLE,
        database_configured=True,
        detail="unsupported",
    )
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.get_audit_store_runtime_status",
        lambda: unsupported_store,
    )
    for target in (
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="redis_queue", worker_mode="DEDICATED"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="filesystem",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.READY,
                root_configured=True,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(startup_readiness_blocking=False, startup_readiness_findings=[])
    )

    dependency = next(
        item for item in status.dependencies if item.dependency_id == "durable_sql_state"
    )
    assert dependency.classification.value == "BLOCKED"
    assert "audit" in dependency.detail


def test_production_baseline_runtime_blocks_unrecognized_queue_worker_artifact_and_rollout_modes(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "azure_blob"
    settings.secret_source_mode = "deployment_managed"
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "DOCUMENTED_ONLY"
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    for target in (
        "get_audit_store_runtime_status",
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="sqs", worker_mode="DEGRADED_FALLBACK"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="azure_blob",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.UNAVAILABLE,
                root_configured=False,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(startup_readiness_blocking=False, startup_readiness_findings=[])
    )

    queue_dependency = next(
        item for item in status.dependencies if item.dependency_id == "async_queue_backend"
    )
    worker_dependency = next(
        item for item in status.dependencies if item.dependency_id == "async_worker_mode"
    )
    artifact_dependency = next(
        item for item in status.dependencies if item.dependency_id == "artifact_object_store"
    )
    rollout_dependency = next(
        item for item in status.dependencies if item.dependency_id == "live_provider_rollout"
    )
    assert queue_dependency.classification.value == "BLOCKED"
    assert worker_dependency.classification.value == "BLOCKED"
    assert artifact_dependency.classification.value == "BLOCKED"
    assert rollout_dependency.classification.value == "FALLBACK"


def test_production_baseline_runtime_blocks_migration_findings_from_startup_state(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = "/data/object-store"
    settings.secret_source_mode = "deployment_managed"
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    for target in (
        "get_audit_store_runtime_status",
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_async_runtime_status",
        lambda: SimpleNamespace(queue_backend="redis_queue", worker_mode="DEDICATED"),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_runtime.build_artifact_runtime_status",
        lambda: SimpleNamespace(
            object_store_mode="filesystem",
            object_store=SimpleNamespace(
                status=RuntimeReadinessStatus.READY,
                root_configured=True,
            ),
        ),
    )

    status = build_production_baseline_runtime_status(
        SimpleNamespace(
            startup_readiness_blocking=True,
            startup_readiness_findings=["retrieval store: migration required"],
        )
    )

    dependency = next(
        item for item in status.dependencies if item.dependency_id == "migration_posture"
    )
    assert dependency.classification.value == "BLOCKED"
    assert "migration required" in status.blocking_findings[-1]
