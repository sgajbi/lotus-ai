"""Runtime profile derives protection defaults (issue #153, S2)."""

from app.config import PROMOTED_PROFILE_DEFAULTS, Settings, settings
from app.services.startup_policy import _provider_protection_findings


def test_local_profile_keeps_light_defaults() -> None:
    local = Settings(runtime_profile="local")
    assert local.provider_retry_limit == 0
    assert local.live_text_quota_enforced is False
    assert local.provider_operations_store_mode == "memory"
    assert local.startup_readiness_policy == "warn"


def test_promoted_profile_derives_the_protection_set() -> None:
    promoted = Settings(runtime_profile="promoted")
    for field_name, expected in PROMOTED_PROFILE_DEFAULTS.items():
        assert getattr(promoted, field_name) == expected, field_name


def test_explicit_operator_choice_beats_the_profile() -> None:
    overridden = Settings(
        runtime_profile="promoted",
        provider_retry_limit=0,
        provider_operations_store_mode="memory",
    )
    assert overridden.provider_retry_limit == 0
    assert overridden.provider_operations_store_mode == "memory"
    # Untouched keys still derive.
    assert overridden.live_text_degradation_enforced is True


def test_promoted_live_mode_without_limits_yields_blocking_findings() -> None:
    settings.runtime_profile = "promoted"
    settings.provider_mode = "openai"
    settings.live_text_quota_enforced = True
    settings.live_text_budget_enforced = True
    settings.live_text_degradation_enforced = True
    settings.provider_operations_store_mode = "memory"

    findings = _provider_protection_findings()

    assert any("no quota limits" in finding for finding in findings)
    assert any("no hard budget" in finding for finding in findings)
    assert any("memory state" in finding for finding in findings)


def test_promoted_live_mode_with_disabled_protection_is_a_finding() -> None:
    settings.runtime_profile = "promoted"
    settings.provider_mode = "openai"
    settings.live_text_quota_enforced = False
    settings.live_text_budget_enforced = False
    settings.live_text_degradation_enforced = False

    findings = _provider_protection_findings()

    assert any("quota: enforcement is disabled" in finding for finding in findings)
    assert any("budget: enforcement is disabled" in finding for finding in findings)
    assert any("breaker enforcement is disabled" in finding for finding in findings)


def test_local_profile_and_stub_mode_produce_no_protection_findings() -> None:
    settings.runtime_profile = "local"
    settings.provider_mode = "openai"
    assert _provider_protection_findings() == []

    settings.runtime_profile = "promoted"
    settings.provider_mode = "disabled"
    assert _provider_protection_findings() == []
