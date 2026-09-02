"""The candidate universe is derived from catalogue evidence bounded by policy.

Issue #244, U1: the derivation is routing-decision evidence only - the
enumeration still comes from configuration, and the universe says so honestly
while recording what the catalogue holds that policy does not let serve. The
equivalence proven here is what makes the U2 flip safe.
"""

from __future__ import annotations

import pytest

from app.contracts.model_catalogue import (
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import (
    CandidateUniverseExclusionReason,
    CandidateUniverseSource,
)
from app.services.model_catalogue import (
    derive_candidate_universe,
    ensure_model_catalogue_seeded,
)
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.provider_execution_config import resolve_provider_execution_config
from tests.unit.test_ordered_fallback_routing import (
    ALTERNATE,
    PRIMARY,
    _install_adapter,
    _ordered_fallback_settings,
    _request,
)

PRIMARY_ENTRY = derive_model_catalogue_entry_id(
    provider_id=PRIMARY, model_revision="gpt-5.4", deployment=None
)
ALTERNATE_ENTRY = derive_model_catalogue_entry_id(
    provider_id=ALTERNATE, model_revision="claude-sonnet-5", deployment=None
)


def test_derived_universe_matches_the_configured_pair() -> None:
    """Equivalence: under current configuration the derivation yields exactly
    the configured primary/fallback order with nothing excluded."""

    _ordered_fallback_settings()
    universe = derive_candidate_universe(resolve_provider_execution_config())

    assert universe.source is CandidateUniverseSource.CONFIGURED
    assert universe.candidate_entry_ids == [PRIMARY_ENTRY, ALTERNATE_ENTRY]
    assert universe.exclusions == []


def test_lifecycle_ineligible_policy_identity_is_excluded_with_its_reason() -> None:
    _ordered_fallback_settings()
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    entry = repository.get_entry(PRIMARY_ENTRY)
    assert entry is not None
    repository.upsert_entry(
        entry.model_copy(update={"lifecycle_state": ModelLifecycleState.DEPRECATED})
    )

    universe = derive_candidate_universe(resolve_provider_execution_config())

    assert universe.candidate_entry_ids == [ALTERNATE_ENTRY]
    assert [e.reason for e in universe.exclusions] == [
        CandidateUniverseExclusionReason.LIFECYCLE_INELIGIBLE
    ]
    assert "DEPRECATED" in universe.exclusions[0].detail


def test_uncatalogued_policy_identity_is_excluded_with_its_reason() -> None:
    """A policy-ordered identity with no catalogue entry cannot earn
    eligibility - the derivation says which identity and why."""

    from dataclasses import replace

    _ordered_fallback_settings()
    config = resolve_provider_execution_config()
    ghost = replace(
        config,
        fallback_provider_id="text.ghost",
        fallback_model_id="phantom-1",
        fallback_model_version=None,
    )

    universe = derive_candidate_universe(ghost)

    assert universe.candidate_entry_ids == [PRIMARY_ENTRY]
    reasons_by_entry = {e.entry_id: e.reason for e in universe.exclusions}
    assert reasons_by_entry["text.ghost:phantom-1"] is (
        CandidateUniverseExclusionReason.MODEL_NOT_CATALOGUED
    )
    # The real configured alternate is still catalogued and serving-eligible;
    # under this policy it is excluded by policy, not misreported as missing.
    assert reasons_by_entry[ALTERNATE_ENTRY] is (CandidateUniverseExclusionReason.POLICY_EXCLUDED)


def test_serving_eligible_entry_outside_policy_is_policy_excluded() -> None:
    """The operator question configuration cannot answer: a serving-eligible
    catalogue entry for this mode that no policy row lets serve is recorded
    as POLICY_EXCLUDED - while an out-of-service non-policy entry is not
    misattributed to policy."""

    _ordered_fallback_settings()
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    template = repository.get_entry(PRIMARY_ENTRY)
    assert template is not None

    def _extra(revision: str, state: ModelLifecycleState) -> None:
        entry_id = derive_model_catalogue_entry_id(
            provider_id=PRIMARY, model_revision=revision, deployment=None
        )
        repository.upsert_entry(
            template.model_copy(
                update={
                    "entry_id": entry_id,
                    "model_revision": revision,
                    "lifecycle_state": state,
                    "seed_source": ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY,
                }
            )
        )

    _extra("gpt-5.5-preview", ModelLifecycleState.APPROVED)
    _extra("gpt-4.9-retired", ModelLifecycleState.RETIRED)

    universe = derive_candidate_universe(resolve_provider_execution_config())

    assert universe.candidate_entry_ids == [PRIMARY_ENTRY, ALTERNATE_ENTRY]
    policy_excluded = [
        e
        for e in universe.exclusions
        if e.reason is CandidateUniverseExclusionReason.POLICY_EXCLUDED
    ]
    assert [e.entry_id for e in policy_excluded] == [f"{PRIMARY}:gpt-5.5-preview"]
    assert all(e.entry_id != f"{PRIMARY}:gpt-4.9-retired" for e in universe.exclusions), (
        "an out-of-service non-policy entry must not be misattributed to policy"
    )


def test_ordered_routing_decision_carries_universe_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every ordered decision records where its enumeration came from and what
    the catalogue holds that policy does not let serve."""

    _ordered_fallback_settings()
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    template = repository.get_entry(PRIMARY_ENTRY)
    assert template is not None
    shadow_id = derive_model_catalogue_entry_id(
        provider_id=PRIMARY, model_revision="gpt-5.5-preview", deployment=None
    )
    repository.upsert_entry(
        template.model_copy(
            update={
                "entry_id": shadow_id,
                "model_revision": "gpt-5.5-preview",
                "lifecycle_state": ModelLifecycleState.APPROVED,
                "seed_source": ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY,
            }
        )
    )
    _install_adapter(monkeypatch, failing={})

    from app.services.provider_gateway import execute_text_generation

    response = execute_text_generation(_request())

    decision = response.routing_decision
    assert decision is not None
    assert decision.universe_source is CandidateUniverseSource.CONFIGURED
    assert [e.entry_id for e in decision.universe_exclusions] == [shadow_id]
    assert decision.universe_exclusions[0].reason is (
        CandidateUniverseExclusionReason.POLICY_EXCLUDED
    )
