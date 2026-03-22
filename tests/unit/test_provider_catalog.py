from app.contracts.providers import ProviderLifecycleStatus
from app.services.provider_catalog import build_provider_catalog


def test_provider_catalog_exposes_documented_disabled_execution_posture() -> None:
    catalog = build_provider_catalog()

    assert catalog.provider_mode == "disabled"
    assert catalog.embedding_provider_mode == "disabled"
    assert catalog.runtime_execution_enabled is False
    assert any(provider.provider_id == "text.stub" for provider in catalog.providers)
    assert all(
        provider.lifecycle_status == ProviderLifecycleStatus.DOCUMENTED
        for provider in catalog.providers
    )
    assert all(provider.enabled_for_execution is False for provider in catalog.providers)
