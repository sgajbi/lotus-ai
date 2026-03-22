from pathlib import Path

from app.config import settings
from app.contracts.providers import ProviderQuotaScope
from app.providers.base import ProviderExecutionError
from app.services.provider_quota_policy import (
    build_provider_quota_policy,
    enforce_provider_quota,
)
from app.services.provider_operations_store import reset_provider_operations_store_cache
from app.services.provider_request_builder import build_provider_execution_request
from app.services.task_execution_pipeline import validate_task_request
from tests.support.migration_runner import upgrade_database_to_head
from tests.unit.test_task_executor import _request


def test_provider_quota_policy_reports_disabled_default_posture() -> None:
    response = build_provider_quota_policy()

    assert response.service == "lotus-ai"
    assert response.provider_mode == "disabled"
    assert response.quota_enforced is False
    assert response.configuration_valid is True
    assert response.matching_order == [
        ProviderQuotaScope.TENANT,
        ProviderQuotaScope.CALLER_APP,
        ProviderQuotaScope.TASK,
        ProviderQuotaScope.DEFAULT,
    ]
    assert response.quotas == []


def test_provider_quota_policy_reports_configured_scopes_and_usage() -> None:
    settings.live_text_quota_enforced = True
    settings.live_text_default_quota_limit = 5
    settings.live_text_task_quota_limits = "explain.v1=2"
    settings.live_text_caller_quota_limits = "lotus-manage=3"
    settings.live_text_tenant_quota_limits = "tenant-sg-001=4"

    request = _request("explain.v1", expected_output_label=None)
    request.caller.requested_by = "ops.user@lotus"
    request.caller.tenant_id = "tenant-sg-001"
    context = validate_task_request(request)
    provider_request = build_provider_execution_request(context=context)

    enforce_provider_quota(provider_request)

    response = build_provider_quota_policy()

    assert response.quota_enforced is True
    assert response.configuration_valid is True
    assert len(response.quotas) == 4
    tenant_quota = next(
        quota for quota in response.quotas if quota.scope == ProviderQuotaScope.TENANT
    )
    caller_quota = next(
        quota for quota in response.quotas if quota.scope == ProviderQuotaScope.CALLER_APP
    )
    task_quota = next(quota for quota in response.quotas if quota.scope == ProviderQuotaScope.TASK)
    default_quota = next(
        quota for quota in response.quotas if quota.scope == ProviderQuotaScope.DEFAULT
    )
    assert tenant_quota.current_request_count == 1
    assert caller_quota.current_request_count == 1
    assert task_quota.current_request_count == 1
    assert default_quota.current_request_count == 1


def test_provider_quota_policy_rejects_malformed_configuration() -> None:
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=0,broken-entry"
    settings.live_text_caller_quota_limits = "lotus-manage=abc"

    response = build_provider_quota_policy()

    assert response.configuration_valid is False
    assert any("must be a positive integer" in finding for finding in response.findings)
    assert any("malformed" in finding for finding in response.findings)


def test_provider_quota_policy_rejects_invalid_task_scope() -> None:
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "knowledge_answer.v1=2"

    response = build_provider_quota_policy()

    assert response.configuration_valid is False
    assert any(
        "not valid for live text-generation quota enforcement" in finding
        for finding in response.findings
    )


def test_provider_quota_policy_rejects_blank_scope_key_and_invalid_default_limit() -> None:
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "=2"
    settings.live_text_default_quota_limit = 0

    response = build_provider_quota_policy()

    assert response.configuration_valid is False
    assert any("non-empty scope key" in finding for finding in response.findings)
    assert any(
        "Default provider quota limit must be a positive integer." in finding
        for finding in response.findings
    )


def test_provider_quota_policy_enforcement_rejects_invalid_configuration() -> None:
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "broken-entry"

    request = _request("explain.v1", expected_output_label=None)
    context = validate_task_request(request)
    provider_request = build_provider_execution_request(context=context)

    try:
        enforce_provider_quota(provider_request)
    except ProviderExecutionError as exc:
        assert exc.category.value == "INVALID_QUOTA_CONFIGURATION"
    else:
        raise AssertionError("Expected invalid quota configuration to block execution")


def test_provider_quota_policy_persists_counts_in_sql_store_across_store_reset(
    tmp_path: Path,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    settings.live_text_quota_enforced = True
    settings.live_text_default_quota_limit = 2
    settings.live_text_task_quota_limits = "explain.v1=2"
    upgrade_database_to_head(settings.database_url)

    request = _request("explain.v1", expected_output_label=None)
    context = validate_task_request(request)
    provider_request = build_provider_execution_request(context=context)

    enforce_provider_quota(provider_request)
    reset_provider_operations_store_cache()

    response = build_provider_quota_policy()

    task_quota = next(quota for quota in response.quotas if quota.scope == ProviderQuotaScope.TASK)
    default_quota = next(
        quota for quota in response.quotas if quota.scope == ProviderQuotaScope.DEFAULT
    )
    assert task_quota.current_request_count == 1
    assert default_quota.current_request_count == 1


def test_provider_quota_policy_durable_enforcement_blocks_on_persisted_limit(
    tmp_path: Path,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=1"
    upgrade_database_to_head(settings.database_url)

    request = _request("explain.v1", expected_output_label=None)
    context = validate_task_request(request)
    provider_request = build_provider_execution_request(context=context)

    enforce_provider_quota(provider_request)
    reset_provider_operations_store_cache()

    try:
        enforce_provider_quota(provider_request)
    except ProviderExecutionError as exc:
        assert exc.category.value == "QUOTA_EXCEEDED"
    else:
        raise AssertionError("Expected persisted quota state to block the second execution")
