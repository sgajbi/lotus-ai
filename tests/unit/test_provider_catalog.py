from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCredentialStatus,
    ProviderFailureCategory,
    ProviderLifecycleStatus,
    ProviderRolloutState,
)
from app.services.provider_catalog import build_provider_catalog


def test_provider_catalog_exposes_documented_disabled_execution_posture() -> None:
    catalog = build_provider_catalog()

    assert catalog.provider_mode == "disabled"
    assert catalog.embedding_provider_mode == "disabled"
    assert catalog.text_generation_configuration.rollout_state == ProviderRolloutState.STUB_DEFAULT
    assert (
        catalog.text_generation_configuration.credential_status
        == ProviderCredentialStatus.NOT_CONFIGURED
    )
    assert catalog.runtime_execution_enabled is False
    assert any(provider.provider_id == "text.stub" for provider in catalog.providers)
    assert any(
        provider.provider_id == "text.openai"
        and provider.adapter_kind == ProviderAdapterKind.OPENAI_LIVE
        and provider.failure_category_on_use == ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
        for provider in catalog.providers
    )
    assert all(
        provider.lifecycle_status == ProviderLifecycleStatus.DOCUMENTED
        for provider in catalog.providers
    )
    assert all(provider.enabled_for_execution is False for provider in catalog.providers)


def test_provider_catalog_marks_openai_provider_executable_when_rollout_allows_it() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    catalog = build_provider_catalog()

    openai_provider = next(
        provider for provider in catalog.providers if provider.provider_id == "text.openai"
    )
    assert catalog.runtime_execution_enabled is True
    assert openai_provider.enabled_for_execution is True
