from __future__ import annotations

from collections import defaultdict

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExpansionPolicyDescriptor,
    ProviderExpansionRuleDescriptor,
)
from app.providers.registry import list_registered_provider_descriptors

_MAX_GOVERNED_PROVIDER_COUNT: dict[ProviderCapability, int] = {
    ProviderCapability.TEXT_GENERATION: 3,
    ProviderCapability.EMBEDDINGS: 3,
}

_EXPANSION_REQUIREMENTS: tuple[str, ...] = (
    "Any additional provider must land behind typed catalog and policy descriptors before activation is considered.",
    "Any additional provider must satisfy the existing evaluation, runbook, quota, budget, degradation, and governance gates before execution is enabled.",
    "No additional provider may bypass bounded rollout or weaken control-plane clarity through implicit fallback behavior.",
)


def build_provider_expansion_policy() -> ProviderExpansionPolicyDescriptor:
    grouped_provider_ids: dict[ProviderCapability, list[str]] = defaultdict(list)
    grouped_live_capable_ids: dict[ProviderCapability, list[str]] = defaultdict(list)

    for descriptor in list_registered_provider_descriptors():
        grouped_provider_ids[descriptor.capability].append(descriptor.provider_id)
        if descriptor.adapter_kind != ProviderAdapterKind.STUB:
            grouped_live_capable_ids[descriptor.capability].append(descriptor.provider_id)

    capability_rules = [
        _build_capability_rule(
            capability=capability,
            registered_provider_ids=grouped_provider_ids.get(capability, []),
            live_capable_provider_ids=grouped_live_capable_ids.get(capability, []),
        )
        for capability in (ProviderCapability.TEXT_GENERATION, ProviderCapability.EMBEDDINGS)
    ]

    expansion_blocked = any(rule.expansion_ready is False for rule in capability_rules)
    findings = [
        "Provider breadth is now governed through explicit per-capability slot limits rather than ad hoc adapter growth.",
    ]
    if expansion_blocked:
        findings.append(
            "At least one capability has exhausted or exceeded the bounded provider breadth model and needs governance review before more providers are registered."
        )
    else:
        findings.append(
            "Each provider capability still has bounded headroom for one later governed provider without widening execution semantics today."
        )

    return ProviderExpansionPolicyDescriptor(
        bounded_expansion_enabled=True,
        expansion_blocked=expansion_blocked,
        findings=findings,
        capability_rules=capability_rules,
    )


def _build_capability_rule(
    *,
    capability: ProviderCapability,
    registered_provider_ids: list[str],
    live_capable_provider_ids: list[str],
) -> ProviderExpansionRuleDescriptor:
    max_governed_provider_count = _MAX_GOVERNED_PROVIDER_COUNT[capability]
    available_expansion_slots = max(max_governed_provider_count - len(registered_provider_ids), 0)
    expansion_ready = len(registered_provider_ids) <= max_governed_provider_count
    notes = (
        "Current provider breadth remains within the governed slot model for this capability."
        if expansion_ready
        else "Current provider breadth exceeds the governed slot model and must be reduced or explicitly re-approved."
    )
    return ProviderExpansionRuleDescriptor(
        capability=capability,
        registered_provider_ids=registered_provider_ids,
        live_capable_provider_ids=live_capable_provider_ids,
        max_governed_provider_count=max_governed_provider_count,
        available_expansion_slots=available_expansion_slots,
        expansion_ready=expansion_ready,
        requirements=list(_EXPANSION_REQUIREMENTS),
        notes=notes,
    )
