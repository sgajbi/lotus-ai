from pathlib import Path
from types import SimpleNamespace

from app.config import settings
from app.services.artifact_store import reset_artifact_store_cache
from app.services.production_baseline_runtime import build_production_baseline_runtime_status
from tests.support.migration_runner import upgrade_database_to_head


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
    reset_artifact_store_cache()

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
    tmp_path: Path, monkeypatch
) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-production-baseline.db'}"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "objects")
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
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()

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
        and dependency.classification.value == "FALLBACK"
        for dependency in status.dependencies
    )
    assert any(
        dependency.dependency_id == "artifact_object_store"
        and dependency.classification.value == "FALLBACK"
        for dependency in status.dependencies
    )
