from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.resilience import (
    ResilienceDeliveryStage,
    ResiliencePosture,
    ResilienceRecoveryState,
    ResilienceRecoveryClassification,
)
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.services.artifact_store import reset_artifact_store_cache
from app.services.resilience_runtime import build_resilience_runtime_status
from tests.support.migration_runner import upgrade_database_to_head


def test_resilience_runtime_defaults_to_local_or_demo_continuity() -> None:
    settings.audit_store_mode = "memory"
    settings.prompt_store_mode = "memory"
    settings.retrieval_store_mode = "memory"
    settings.access_control_store_mode = "memory"
    settings.provider_operations_store_mode = "memory"
    settings.async_runtime_store_mode = "memory"
    settings.evaluation_runtime_store_mode = "memory"
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.provider_mode = "disabled"
    reset_artifact_store_cache()

    status = build_resilience_runtime_status()

    assert status.delivery_stage is ResilienceDeliveryStage.DRILL_VERIFIED
    assert status.recovery_state is ResilienceRecoveryState.DEGRADED
    assert status.posture is ResiliencePosture.LOCAL_OR_DEMO_CONTINUITY
    assert status.authoritative_dependency_count >= 8
    assert status.restart_survivable_dependency_count == 0
    assert any(
        dependency.dependency_id == "audit_store"
        and dependency.recovery_classification
        is ResilienceRecoveryClassification.DOCUMENTED_FALLBACK
        for dependency in status.dependencies
    )


def test_resilience_runtime_reports_inventory_for_prod_shaped_sql_posture(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-resilience.db'}"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "object-store")
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    settings.retrieval_mode = "disabled"
    settings.provider_mode = "disabled"
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()

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
        monkeypatch.setattr(f"app.services.resilience_runtime.{target}", lambda: ready_store)

    status = build_resilience_runtime_status()

    assert status.delivery_stage is ResilienceDeliveryStage.DRILL_VERIFIED
    assert status.recovery_state is ResilienceRecoveryState.DEGRADED
    assert status.posture is ResiliencePosture.PARTIAL_RUNTIME_DURABILITY
    assert status.restart_survivable_dependency_count >= 10
    assert any(
        dependency.dependency_id == "artifact_object_store"
        and dependency.recovery_classification
        is ResilienceRecoveryClassification.EXTERNAL_RECOVERY_REQUIRED
        for dependency in status.dependencies
    )
    assert any(
        dependency.dependency_id == "artifact_object_store"
        and dependency.recovery_state is ResilienceRecoveryState.RESTORED_WITH_FINDINGS
        for dependency in status.dependencies
    )


def test_resilience_runtime_reports_restored_with_findings_when_runtime_dependencies_are_steady(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-resilience-restored.db'}"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "object-store")
    settings.retrieval_mode = "disabled"
    settings.provider_mode = "disabled"
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()

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
        monkeypatch.setattr(f"app.services.resilience_runtime.{target}", lambda: ready_store)
    monkeypatch.setattr(
        "app.services.resilience_runtime.build_async_runtime_status",
        lambda: type(
            "AsyncRuntime",
            (),
            {
                "queue_backend": "redis_queue",
                "worker_mode": "DEDICATED",
                "degraded_findings": [],
            },
        )(),
    )

    status = build_resilience_runtime_status()

    assert status.recovery_state is ResilienceRecoveryState.RESTORED_WITH_FINDINGS
    assert any(
        dependency.dependency_id == "artifact_object_store"
        and dependency.recovery_state is ResilienceRecoveryState.RESTORED_WITH_FINDINGS
        for dependency in status.dependencies
    )


def test_resilience_runtime_surfaces_degraded_runtime_dependencies(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.resilience_runtime.build_async_runtime_status",
        lambda: type(
            "AsyncRuntime",
            (),
            {
                "queue_backend": "redis_queue",
                "worker_mode": "DEDICATED",
                "degraded_findings": [
                    "Managed queue backend is unavailable; queue-backed async delivery cannot currently be treated as healthy."
                ],
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.resilience_runtime.build_provider_operations_status",
        lambda: type(
            "ProviderOperations",
            (),
            {
                "operations_state": type("OpsState", (), {"value": "CIRCUIT_OPEN"})(),
                "runtime_execution_enabled": True,
                "blocking_reasons": ["Provider circuit breaker is currently open."],
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.resilience_runtime.build_retrieval_execution_status",
        lambda: type(
            "RetrievalExecution",
            (),
            {
                "retrieval_mode": "enabled",
                "execution_stage": type("Stage", (), {"value": "INDEXING_DISABLED"})(),
                "split_route_degraded": True,
                "split_route_findings": ["Retrieval split route is degraded."],
                "message": "Retrieval execution is currently degraded.",
            },
        )(),
    )

    status = build_resilience_runtime_status()

    assert status.recovery_state is ResilienceRecoveryState.DEGRADED
    assert status.recovery_attention_dependency_count >= 3
    assert any(
        finding.startswith("async_queue_backend:")
        for finding in status.recovery_findings
    )
    assert any(
        dependency.dependency_id == "live_provider_dependency"
        and dependency.recovery_state is ResilienceRecoveryState.DEGRADED
        for dependency in status.dependencies
    )
    assert any(
        dependency.dependency_id == "retrieval_execution_path"
        and dependency.recovery_state is ResilienceRecoveryState.DEGRADED
        for dependency in status.dependencies
    )
