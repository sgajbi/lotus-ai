from types import SimpleNamespace

from app.services.platform_status import (
    _resolve_startup_readiness_state,
    build_platform_runtime_status,
)


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
    assert status.retrieval_governance.blocking_area_count == 3
    assert status.prompt_governance.blocking_area_count == 3
    assert status.evaluation_runtime.manifest_version == "foundation.v1"
    assert status.safety_runtime.runtime_redaction_active is False
    assert status.startup_readiness_blocking is True
    assert status.startup_readiness_warnings == ["audit store: configuration required"]
