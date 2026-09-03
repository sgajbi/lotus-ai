"""Runtime profile derives protection defaults (issue #153, S2)."""

import pytest

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
    settings.workflow_pack_admission_store_mode = "sqlalchemy"
    # Non-live provider mode clears the provider findings; the admission
    # store finding is profile-gated regardless of provider mode.
    assert _provider_protection_findings() == []
    settings.workflow_pack_admission_store_mode = "memory"
    assert _provider_protection_findings() == [
        "workflow-pack admission store: per-process memory leases cannot bound "
        "queue admission across replicas in the promoted profile"
    ]


def test_explicitly_weakened_protections_are_captured_loudly() -> None:
    """Issue #233: explicit override still wins, but never silently - every
    protection field explicitly weaker than the promoted default is captured
    at construction, where model_fields_set is authoritative."""

    weakened = Settings(
        runtime_profile="promoted",
        startup_readiness_policy="warn",
        provider_operations_store_mode="memory",
        live_text_budget_enforced=False,
    )
    captured = weakened.promoted_protection_overrides
    assert len(captured) == 3
    assert any("startup_readiness_policy" in finding for finding in captured)
    assert any("provider_operations_store_mode" in finding for finding in captured)
    assert any("live_text_budget_enforced" in finding for finding in captured)
    assert all("explicitly weakened" in finding for finding in captured)

    # An explicit value EQUAL to the promoted default is not a weakening, a
    # weakened tuning value is not a protection override, and outside the
    # promoted profile nothing is captured.
    assert (
        Settings(
            runtime_profile="promoted",
            startup_readiness_policy="enforce",
            provider_retry_limit=0,
        ).promoted_protection_overrides
        == []
    )
    assert Settings(runtime_profile="local").promoted_protection_overrides == []

    # Billing-truth posture is a protection (issue #232): actual_only can only
    # understate spend, so choosing it in promoted is loud.
    billing_weakened = Settings(
        runtime_profile="promoted", provider_failed_attempt_cost_posture="actual_only"
    ).promoted_protection_overrides
    assert len(billing_weakened) == 1
    assert "provider_failed_attempt_cost_posture" in billing_weakened[0]


def test_startup_readiness_surfaces_promoted_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The captured overrides ride the startup findings, so a weakened
    startup policy is loud even though - by the operator's own choice - it
    no longer blocks."""

    from app.services.startup_policy import evaluate_startup_readiness

    monkeypatch.setattr(
        settings,
        "_promoted_protection_overrides",
        [
            "promoted override: startup_readiness_policy is explicitly weakened to "
            "'warn' (promoted default 'enforce'); this protection is operator-overridden"
        ],
    )

    evaluation = evaluate_startup_readiness()

    assert any("promoted override: startup_readiness_policy" in f for f in evaluation.findings)
