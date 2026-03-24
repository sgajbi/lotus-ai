from types import SimpleNamespace

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.services.production_baseline_runtime import build_production_baseline_runtime_status


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
    monkeypatch,
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
        lambda: SimpleNamespace(object_store_mode="filesystem"),
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
