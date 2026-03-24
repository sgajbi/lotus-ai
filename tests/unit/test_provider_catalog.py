from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
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
    assert catalog.embedding_configuration.rollout_state == ProviderRolloutState.DOCUMENTED_ONLY
    assert (
        catalog.text_generation_configuration.credential_status
        == ProviderCredentialStatus.NOT_CONFIGURED
    )
    assert (
        catalog.embedding_configuration.credential_status == ProviderCredentialStatus.NOT_CONFIGURED
    )
    assert catalog.runtime_execution_enabled is False
    assert catalog.text_generation_runtime_execution_enabled is False
    assert catalog.embedding_runtime_execution_enabled is False
    assert catalog.expansion_policy.bounded_expansion_enabled is True
    assert catalog.expansion_policy.expansion_blocked is False
    assert any(provider.provider_id == "text.stub" for provider in catalog.providers)
    assert any(
        provider.provider_id == "text.openai"
        and provider.adapter_kind == ProviderAdapterKind.OPENAI_LIVE
        and provider.failure_category_on_use == ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
        for provider in catalog.providers
    )
    assert any(
        provider.provider_id == "embeddings.openai"
        and provider.capability == ProviderCapability.EMBEDDINGS
        and provider.adapter_kind == ProviderAdapterKind.OPENAI_EMBEDDINGS_LIVE
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
    assert catalog.text_generation_runtime_execution_enabled is True
    assert catalog.embedding_runtime_execution_enabled is False
    text_rule = next(
        rule
        for rule in catalog.expansion_policy.capability_rules
        if rule.capability == ProviderCapability.TEXT_GENERATION
    )
    assert text_rule.live_capable_provider_ids == ["text.openai"]
    assert openai_provider.enabled_for_execution is True


def test_provider_catalog_exposes_live_embedding_path_without_enabling_execution() -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    catalog = build_provider_catalog()

    openai_embedding_provider = next(
        provider for provider in catalog.providers if provider.provider_id == "embeddings.openai"
    )
    assert catalog.embedding_configuration.configuration_valid is True
    assert catalog.embedding_configuration.credential_status == ProviderCredentialStatus.CONFIGURED
    assert openai_embedding_provider.runtime_mode == "enabled"
    assert catalog.embedding_runtime_execution_enabled is True
    embedding_rule = next(
        rule
        for rule in catalog.expansion_policy.capability_rules
        if rule.capability == ProviderCapability.EMBEDDINGS
    )
    assert embedding_rule.available_expansion_slots == 1
    assert openai_embedding_provider.enabled_for_execution is True
