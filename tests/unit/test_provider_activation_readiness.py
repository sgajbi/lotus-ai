from app.config import settings
from app.contracts.providers import ProviderCredentialStatus, ProviderRolloutState
from app.services.provider_activation_readiness import build_provider_activation_readiness


def test_provider_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_provider_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.activation_ready is False
    assert readiness.provider_mode == "disabled"
    assert readiness.embedding_provider_mode == "disabled"
    assert (
        readiness.text_generation_configuration.rollout_state == ProviderRolloutState.STUB_DEFAULT
    )
    assert (
        readiness.text_generation_configuration.credential_status
        == ProviderCredentialStatus.NOT_CONFIGURED
    )
    assert len(readiness.blocking_findings) == 5
    assert len(readiness.activation_path) == 5


def test_provider_activation_readiness_reports_invalid_live_configuration() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"

    readiness = build_provider_activation_readiness()

    assert readiness.text_generation_configuration.configuration_valid is False
    assert any("partially populated" in finding for finding in readiness.blocking_findings)
