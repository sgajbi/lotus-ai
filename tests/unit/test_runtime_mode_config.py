"""Per-execution runtime-mode config and store-mode override (issue #148, S4)."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from app.config import settings
from app.services.provider_operations_store import (
    override_provider_operations_store_mode,
    resolved_provider_operations_store_mode,
)
from app.services.runtime_mode_config import (
    get_runtime_mode_config_override,
    override_runtime_mode_config,
    resolve_runtime_mode_config,
)


def test_runtime_modes_resolve_from_settings_and_override_wins() -> None:
    base = resolve_runtime_mode_config()
    assert base.retrieval_mode == settings.retrieval_mode
    assert base.safety_mode == settings.safety_mode
    assert base.embedding_provider_mode == settings.embedding_provider_mode
    assert get_runtime_mode_config_override() is None

    case_modes = replace(base, retrieval_mode="enabled", safety_mode="runtime_enforced")
    with override_runtime_mode_config(case_modes):
        assert resolve_runtime_mode_config() is case_modes
        # Execution-scoped: a concurrent request on another thread still
        # resolves the settings-derived modes.
        with ThreadPoolExecutor(max_workers=1) as executor:
            other = executor.submit(resolve_runtime_mode_config).result()
        assert other.retrieval_mode == settings.retrieval_mode
        assert other.safety_mode == settings.safety_mode

    assert get_runtime_mode_config_override() is None
    assert settings.retrieval_mode == "disabled"


def test_store_mode_override_is_execution_scoped() -> None:
    assert resolved_provider_operations_store_mode() == settings.provider_operations_store_mode

    with override_provider_operations_store_mode("sqlalchemy"):
        assert resolved_provider_operations_store_mode() == "sqlalchemy"
        with ThreadPoolExecutor(max_workers=1) as executor:
            other = executor.submit(resolved_provider_operations_store_mode).result()
        assert other == settings.provider_operations_store_mode
        assert settings.provider_operations_store_mode == "memory"

    assert resolved_provider_operations_store_mode() == settings.provider_operations_store_mode
