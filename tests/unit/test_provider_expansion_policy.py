from _pytest.monkeypatch import MonkeyPatch

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
)
from app.providers.base import ProviderAdapterDescriptor
from app.services.provider_expansion_policy import build_provider_expansion_policy


def test_provider_expansion_policy_reports_bounded_headroom_per_capability() -> None:
    policy = build_provider_expansion_policy()

    assert policy.bounded_expansion_enabled is True
    assert policy.expansion_blocked is False
    assert len(policy.capability_rules) == 2

    text_rule = next(
        rule
        for rule in policy.capability_rules
        if rule.capability == ProviderCapability.TEXT_GENERATION
    )
    embedding_rule = next(
        rule for rule in policy.capability_rules if rule.capability == ProviderCapability.EMBEDDINGS
    )

    assert text_rule.registered_provider_ids == ["text.stub", "text.openai"]
    assert text_rule.live_capable_provider_ids == ["text.openai"]
    assert text_rule.max_governed_provider_count == 3
    assert text_rule.available_expansion_slots == 1
    assert text_rule.expansion_ready is True

    assert embedding_rule.registered_provider_ids == ["embeddings.stub", "embeddings.openai"]
    assert embedding_rule.live_capable_provider_ids == ["embeddings.openai"]
    assert embedding_rule.max_governed_provider_count == 3
    assert embedding_rule.available_expansion_slots == 1
    assert embedding_rule.expansion_ready is True


def test_provider_expansion_policy_blocks_when_registered_breadth_exceeds_bounded_limit(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.provider_expansion_policy.list_registered_provider_descriptors",
        lambda: [
            ProviderAdapterDescriptor(
                provider_id="text.stub",
                display_name="Stub",
                capability=ProviderCapability.TEXT_GENERATION,
                adapter_kind=ProviderAdapterKind.STUB,
                runtime_mode=ProviderExecutionMode.STUB,
                enabled_for_execution=False,
                source_reference="tests",
                notes="stub",
            ),
            ProviderAdapterDescriptor(
                provider_id="text.openai",
                display_name="OpenAI",
                capability=ProviderCapability.TEXT_GENERATION,
                adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
                runtime_mode=ProviderExecutionMode.OPENAI,
                enabled_for_execution=False,
                source_reference="tests",
                notes="live",
            ),
            ProviderAdapterDescriptor(
                provider_id="text.alt.one",
                display_name="Alt One",
                capability=ProviderCapability.TEXT_GENERATION,
                adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
                runtime_mode=ProviderExecutionMode.OPENAI,
                enabled_for_execution=False,
                source_reference="tests",
                notes="candidate",
            ),
            ProviderAdapterDescriptor(
                provider_id="text.alt.two",
                display_name="Alt Two",
                capability=ProviderCapability.TEXT_GENERATION,
                adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
                runtime_mode=ProviderExecutionMode.OPENAI,
                enabled_for_execution=False,
                source_reference="tests",
                notes="candidate",
            ),
        ],
    )

    policy = build_provider_expansion_policy()

    text_rule = next(
        rule
        for rule in policy.capability_rules
        if rule.capability == ProviderCapability.TEXT_GENERATION
    )
    assert policy.expansion_blocked is True
    assert text_rule.available_expansion_slots == 0
    assert text_rule.expansion_ready is False
    assert "exhausted or exceeded" in policy.findings[1]
