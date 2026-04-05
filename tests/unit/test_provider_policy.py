from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderCredentialStatus,
    ProviderFailureCategory,
    ProviderRolloutState,
)
from app.services.provider_policy import build_provider_policy
from app.services.provider_policy import require_supported_embedding_mode
from app.services.provider_policy import require_supported_text_generation_mode


def test_provider_policy_reports_supported_modes_and_rejection_behavior() -> None:
    response = build_provider_policy()

    assert response.service == "lotus-ai"
    assert response.text_generation_configuration.rollout_state == ProviderRolloutState.STUB_DEFAULT
    assert (
        response.text_generation_configuration.credential_status
        == ProviderCredentialStatus.NOT_CONFIGURED
    )
    assert len(response.policies) == 2
    assert response.expansion_policy.bounded_expansion_enabled is True
    assert response.expansion_policy.expansion_blocked is False
    text_policy = next(
        policy
        for policy in response.policies
        if policy.capability == ProviderCapability.TEXT_GENERATION
    )
    assert text_policy.configured_mode == "disabled"
    assert [mode.value for mode in text_policy.allowed_modes] == [
        "disabled",
        "stub",
        "openai",
        "local_openai_compatible",
    ]
    assert text_policy.selected_provider_id == "text.stub"
    assert text_policy.selected_adapter_kind == ProviderAdapterKind.STUB
    assert text_policy.live_execution_enabled is False
    assert text_policy.rejection_category == ProviderFailureCategory.UNSUPPORTED_MODE


def test_provider_policy_reports_openai_selection_when_live_mode_is_requested() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    response = build_provider_policy()

    text_policy = next(
        policy
        for policy in response.policies
        if policy.capability == ProviderCapability.TEXT_GENERATION
    )
    text_rule = next(
        rule
        for rule in response.expansion_policy.capability_rules
        if rule.capability == ProviderCapability.TEXT_GENERATION
    )
    assert text_policy.selected_provider_id == "text.openai"
    assert text_policy.selected_adapter_kind == ProviderAdapterKind.OPENAI_LIVE
    assert text_policy.rejection_category == ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED
    assert text_rule.available_expansion_slots == 1


def test_provider_policy_reports_local_openai_compatible_selection_when_requested() -> None:
    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "explain.v1"

    response = build_provider_policy()

    text_policy = next(
        policy
        for policy in response.policies
        if policy.capability == ProviderCapability.TEXT_GENERATION
    )
    assert text_policy.selected_provider_id == "text.local"
    assert text_policy.selected_adapter_kind == ProviderAdapterKind.OPENAI_COMPATIBLE_LOCAL
    assert text_policy.rejection_category == ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED


def test_provider_policy_rejects_unknown_runtime_mode() -> None:
    settings.provider_mode = "unsupported"

    try:
        require_supported_text_generation_mode()
    except Exception as exc:
        assert "not supported in the current phase" in str(exc)
    else:
        raise AssertionError("Expected runtime-mode rejection for unsupported provider mode")


def test_provider_policy_reports_unresolved_provider_for_unsupported_mode() -> None:
    settings.provider_mode = "unsupported"

    response = build_provider_policy()

    text_policy = next(
        policy
        for policy in response.policies
        if policy.capability == ProviderCapability.TEXT_GENERATION
    )
    assert text_policy.selected_provider_id == "text.unresolved"


def test_provider_policy_rejects_unknown_embedding_mode() -> None:
    settings.embedding_provider_mode = "unsupported"

    try:
        require_supported_embedding_mode()
    except Exception as exc:
        assert "not supported in the current phase" in str(exc)
    else:
        raise AssertionError("Expected runtime-mode rejection for unsupported embedding mode")


def test_provider_policy_reports_unresolved_embedding_provider_for_unsupported_mode() -> None:
    settings.embedding_provider_mode = "unsupported"

    response = build_provider_policy()

    embedding_policy = next(
        policy for policy in response.policies if policy.capability == ProviderCapability.EMBEDDINGS
    )
    assert embedding_policy.selected_provider_id == "embeddings.unresolved"
