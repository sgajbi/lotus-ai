from app.config import settings
from app.contracts.providers import ProviderCredentialStatus, ProviderRolloutState
from app.services.provider_configuration_status import build_embedding_configuration_status


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

    assert configuration.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED
    assert configuration.credential_status == ProviderCredentialStatus.CONFIGURED
    assert configuration.configuration_valid is True
    assert any("still blocked" in finding for finding in configuration.findings)
