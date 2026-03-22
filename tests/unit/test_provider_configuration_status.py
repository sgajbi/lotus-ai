from app.config import settings
from app.contracts.providers import ProviderCredentialStatus, ProviderRolloutState
from app.services.provider_configuration_status import (
    build_text_generation_configuration_status,
)


def test_provider_configuration_status_reports_foundation_defaults() -> None:
    status = build_text_generation_configuration_status()

    assert status.rollout_state == ProviderRolloutState.STUB_DEFAULT
    assert status.credential_status == ProviderCredentialStatus.NOT_CONFIGURED
    assert status.configuration_valid is True
    assert status.configured_live_provider_id is None
    assert status.configured_live_model_id is None


def test_provider_configuration_status_reports_allowlisted_disabled_configuration() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1,summarize.v1"

    status = build_text_generation_configuration_status()

    assert status.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED
    assert status.credential_status == ProviderCredentialStatus.CONFIGURED
    assert status.configuration_valid is True
    assert status.configured_live_provider_id == "text.openai"
    assert status.configured_live_model_id == "gpt-5.4"
    assert status.allowlisted_task_ids == ["explain.v1", "summarize.v1"]


def test_provider_configuration_status_rejects_partial_live_configuration() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"

    status = build_text_generation_configuration_status()

    assert status.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED
    assert status.credential_status == ProviderCredentialStatus.INVALID
    assert status.configuration_valid is False
    assert any("partially populated" in finding for finding in status.findings)


def test_provider_configuration_status_rejects_missing_task_allowlist_for_live_rollout() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"

    status = build_text_generation_configuration_status()

    assert status.configuration_valid is False
    assert any("allowlisted task id" in finding for finding in status.findings)


def test_provider_configuration_status_rejects_unknown_rollout_state() -> None:
    settings.provider_rollout_state = "UNRECOGNIZED"

    status = build_text_generation_configuration_status()

    assert status.rollout_state == ProviderRolloutState.DOCUMENTED_ONLY
    assert status.configuration_valid is False
    assert any("not recognized" in finding for finding in status.findings)


def test_provider_configuration_status_rejects_unknown_live_provider_id() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.unknown"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    status = build_text_generation_configuration_status()

    assert status.configuration_valid is False
    assert any("not recognized" in finding for finding in status.findings)


def test_provider_configuration_status_rejects_invalid_allowlisted_tasks() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "knowledge_answer.v1"

    status = build_text_generation_configuration_status()

    assert status.configuration_valid is False
    assert any(
        "task allowlist contains unknown or retrieval-backed task ids" in finding
        for finding in status.findings
    )


def test_provider_configuration_status_reports_preconfigured_values_below_live_rollout() -> None:
    settings.provider_rollout_state = "STUB_DEFAULT"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"

    status = build_text_generation_configuration_status()

    assert status.configuration_valid is True
    assert any(
        "rollout remains below live activation posture" in finding for finding in status.findings
    )
