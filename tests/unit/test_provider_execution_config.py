"""Per-request provider execution config (issue #148, S2)."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from app.config import settings
from app.contracts.tasks import OutputLabel
from app.services.provider_execution_config import (
    get_provider_execution_config_override,
    override_provider_execution_config,
    resolve_provider_execution_config,
)
from tests.unit.test_task_executor import _request as _task_request


def test_resolve_reflects_settings_and_override_wins() -> None:
    base = resolve_provider_execution_config()
    assert base.provider_mode == settings.provider_mode
    assert base.api_base == settings.live_text_api_base
    assert get_provider_execution_config_override() is None

    case_config = replace(base, provider_mode="stub", model_id="case-model")
    with override_provider_execution_config(case_config):
        assert resolve_provider_execution_config() is case_config
        # The override is execution-scoped: another thread (a concurrent
        # production request) still resolves the settings-derived config.
        with ThreadPoolExecutor(max_workers=1) as executor:
            other = executor.submit(resolve_provider_execution_config).result()
        assert other.provider_mode == settings.provider_mode
        assert other.model_id != "case-model"

    assert get_provider_execution_config_override() is None


def test_enforcement_thresholds_resolve_from_override_not_settings() -> None:
    from app.services.provider_budget_policy import build_provider_budget_policy
    from app.services.provider_quota_policy import parse_provider_quota_policy

    base = resolve_provider_execution_config()
    assert base.enforcement.quota_enforced is settings.live_text_quota_enforced
    assert base.enforcement.hard_budget_usd == settings.live_text_hard_budget_usd

    case_config = replace(
        base,
        enforcement=replace(
            base.enforcement,
            quota_enforced=True,
            task_quota_limits="explain.v1=5",
            budget_enforced=True,
            hard_budget_usd=2.0,
            soft_budget_usd=0.5,
        ),
    )
    with override_provider_execution_config(case_config):
        parsed = parse_provider_quota_policy()
        assert parsed.quota_enforced is True
        assert any(quota.scope_key == "explain.v1" for quota in parsed.quotas)
        budget = build_provider_budget_policy()
        assert budget.budget_enforced is True
        assert budget.hard_budget_usd == 2.0

    # The override never touched process settings.
    assert settings.live_text_quota_enforced is False
    assert settings.live_text_budget_enforced is False
    assert parse_provider_quota_policy().quota_enforced is False


def test_concurrent_executions_use_independent_configs() -> None:
    """The issue #148 evaluation condition, at the task-executor boundary:

    a request under a config override and a plain production request run
    concurrently; each audit record carries the identity of ITS config, and
    process settings are untouched afterwards.
    """

    from app.services.task_executor import execute_task

    request = _task_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    override_config = replace(resolve_provider_execution_config(), provider_mode="stub")

    with override_provider_execution_config(override_config):
        with ThreadPoolExecutor(max_workers=1) as executor:
            production_future = executor.submit(execute_task, request)
            overridden_response = execute_task(request)
            production_response = production_future.result()

    # The stub adapter reports the provider mode of the config it executed
    # under - the override never leaked into the concurrent request.
    assert overridden_response.audit.provider_mode == "stub"
    assert production_response.audit.provider_mode == settings.provider_mode
    assert settings.provider_mode == "disabled"
    assert resolve_provider_execution_config().provider_mode == "disabled"
