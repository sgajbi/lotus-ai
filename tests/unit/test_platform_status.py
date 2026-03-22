from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.services.platform_status import (
    _resolve_startup_readiness_state,
    build_platform_runtime_status,
)
from app.services.provider_degradation_state import record_provider_failure
from app.services.provider_operations_store import reset_provider_operations_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def test_resolve_startup_readiness_state_defaults_when_app_state_missing() -> None:
    startup_state = _resolve_startup_readiness_state(None)

    assert startup_state.blocking is False
    assert startup_state.warnings == []


def test_resolve_startup_readiness_state_reads_blocking_and_findings() -> None:
    startup_state = _resolve_startup_readiness_state(
        SimpleNamespace(
            startup_readiness_blocking=True,
            startup_readiness_findings=["retrieval store: migration required"],
        )
    )

    assert startup_state.blocking is True
    assert startup_state.warnings == ["retrieval store: migration required"]


def test_build_platform_runtime_status_includes_startup_readiness_state() -> None:
    status = build_platform_runtime_status(
        SimpleNamespace(
            startup_readiness_blocking=True,
            startup_readiness_findings=["audit store: configuration required"],
        )
    )

    assert status.service == "lotus-ai"
    assert status.async_runtime.queue_mode == "DISABLED"
    assert status.provider_governance.blocking_area_count == 3
    assert status.provider_operations.operations_state.value == "ROLLOUT_BLOCKED"
    assert status.retrieval_governance.blocking_area_count == 3
    assert status.prompt_governance.blocking_area_count == 3
    assert status.evaluation_runtime.manifest_version == "foundation.v1"
    assert status.task_runtime.enabled_task_count >= 7
    assert status.task_runtime.retrieval_backed_task_count == 2
    assert status.task_runtime.tasks[0].task_id == "explain.v1"
    assert status.safety_runtime.runtime_redaction_active is False
    assert status.startup_readiness_blocking is True
    assert status.startup_readiness_warnings == ["audit store: configuration required"]


def test_build_platform_runtime_status_reflects_durable_provider_operations_posture(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-platform-status.db'}"
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: fixed_now)

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    reset_provider_operations_store_cache()

    status = build_platform_runtime_status(None)

    assert status.provider_operations.operations_state.value == "CIRCUIT_OPEN"
    assert status.provider_operations.degradation_status.status == "CIRCUIT_OPEN"
    assert status.provider_operations.degradation_status.timeout_failure_count == 1
    assert status.provider_operations.degradation_status.upstream_error_failure_count == 1
