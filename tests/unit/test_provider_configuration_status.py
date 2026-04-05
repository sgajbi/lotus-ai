from app.config import settings
from app.contracts.providers import ProviderCredentialStatus, ProviderRolloutState
from app.services.provider_configuration_status import (
    build_embedding_configuration_status,
    build_text_generation_configuration_status,
)


def test_embedding_configuration_defaults_to_documented_only() -> None:
    configuration = build_embedding_configuration_status()

    assert configuration.capability == "EMBEDDINGS"
    assert configuration.rollout_state == ProviderRolloutState.DOCUMENTED_ONLY
    assert configuration.credential_status == ProviderCredentialStatus.NOT_CONFIGURED
    assert configuration.configuration_valid is True


def test_embedding_configuration_reports_live_path_defined_but_not_activated() -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.openai"
    settings.live_embedding_model_id = "text-embedding-3-large"
    settings.live_embedding_provider_api_key = "secret"

    configuration = build_embedding_configuration_status()

    assert configuration.rollout_state == ProviderRolloutState.CANARY_ENABLED
    assert configuration.credential_status == ProviderCredentialStatus.CONFIGURED
    assert configuration.configuration_valid is True
    assert any("bounded rollout" in finding for finding in configuration.findings)


def test_text_generation_configuration_rejects_unknown_rollout_state() -> None:
    settings.provider_rollout_state = "unknown"

    configuration = build_text_generation_configuration_status()

    assert configuration.rollout_state == ProviderRolloutState.DOCUMENTED_ONLY
    assert configuration.configuration_valid is False
    assert any("not recognized" in finding for finding in configuration.findings)


def test_text_generation_configuration_rejects_unknown_provider_and_partial_values() -> None:
    settings.provider_rollout_state = "documented_only"
    settings.live_text_provider_id = "text.unknown"
    settings.live_text_model_id = "gpt-test"

    configuration = build_text_generation_configuration_status()

    assert configuration.credential_status == ProviderCredentialStatus.INVALID
    assert configuration.configuration_valid is False
    assert any("not recognized" in finding for finding in configuration.findings)
    assert any("partially populated" in finding for finding in configuration.findings)
    assert any(
        "present, but rollout remains below live activation" in finding
        for finding in configuration.findings
    )


def test_text_generation_configuration_accepts_local_openai_compatible_mode_without_api_key() -> (
    None
):
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_provider_api_key = None
    settings.live_text_allowed_task_ids = "explain.v1"

    configuration = build_text_generation_configuration_status()

    assert configuration.credential_status == ProviderCredentialStatus.CONFIGURED
    assert configuration.configuration_valid is True


def test_text_generation_configuration_rejects_local_mode_using_default_openai_api_base() -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "https://api.openai.com/v1"
    settings.live_text_provider_api_key = None
    settings.live_text_allowed_task_ids = "explain.v1"

    configuration = build_text_generation_configuration_status()

    assert configuration.configuration_valid is False
    assert any(
        "non-default local or self-hosted API base" in finding for finding in configuration.findings
    )


def test_embedding_configuration_reports_stub_rollout() -> None:
    settings.embedding_provider_mode = "stub"

    configuration = build_embedding_configuration_status()

    assert configuration.rollout_state == ProviderRolloutState.STUB_DEFAULT
    assert configuration.credential_status == ProviderCredentialStatus.NOT_CONFIGURED
    assert configuration.configuration_valid is True
    assert any("stub path" in finding for finding in configuration.findings)


def test_embedding_configuration_rejects_missing_live_values() -> None:
    settings.embedding_provider_mode = "enabled"

    configuration = build_embedding_configuration_status()

    assert configuration.rollout_state == ProviderRolloutState.CANARY_ENABLED
    assert configuration.credential_status == ProviderCredentialStatus.NOT_CONFIGURED
    assert configuration.configuration_valid is False
    assert any("requires configured provider id" in finding for finding in configuration.findings)


def test_embedding_configuration_rejects_partial_and_unknown_live_provider() -> None:
    settings.embedding_provider_mode = "enabled"
    settings.live_embedding_provider_id = "embeddings.other"
    settings.live_embedding_provider_api_key = "secret"

    configuration = build_embedding_configuration_status()

    assert configuration.credential_status == ProviderCredentialStatus.INVALID
    assert configuration.configuration_valid is False
    assert any("not recognized" in finding for finding in configuration.findings)
    assert any("partially populated" in finding for finding in configuration.findings)


def test_embedding_configuration_rejects_unknown_mode() -> None:
    settings.embedding_provider_mode = "mystery"

    configuration = build_embedding_configuration_status()

    assert configuration.rollout_state == ProviderRolloutState.DOCUMENTED_ONLY
    assert configuration.credential_status == ProviderCredentialStatus.INVALID
    assert configuration.configuration_valid is False
    assert any("not recognized" in finding for finding in configuration.findings)
