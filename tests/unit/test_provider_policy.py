from app.contracts.providers import ProviderCapability
from app.services.provider_policy import build_provider_policy


def test_provider_policy_reports_supported_modes_and_rejection_behavior() -> None:
    response = build_provider_policy()

    assert response.service == "lotus-ai"
    assert len(response.policies) == 2
    text_policy = next(
        policy
        for policy in response.policies
        if policy.capability == ProviderCapability.TEXT_GENERATION
    )
    assert text_policy.configured_mode == "disabled"
    assert [mode.value for mode in text_policy.allowed_modes] == ["disabled", "stub"]
    assert text_policy.selected_provider_id == "text.stub"
    assert text_policy.live_execution_enabled is False
