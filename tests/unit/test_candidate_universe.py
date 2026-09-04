"""The candidate universe is derived from catalogue evidence bounded by policy.

Issue #244, U2: the derivation IS the ordered enumeration - an identity the
catalogue excludes never becomes a candidate, its reasoned exclusion rides the
routing decision, and an empty universe refuses with every reason. The
configured pair supplies policy order and connection material only.
"""

from __future__ import annotations

import pytest

from app.contracts.model_catalogue import (
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_candidate_identity_v2,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import (
    CandidateUniverseExclusionReason,
    CandidateUniverseSource,
    ProviderFailureCategory,
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
# The universe enumerates CANONICAL candidate identities (issue #314);
# exclusions keep the human-readable row keys for operator legibility.
PRIMARY_CANONICAL = derive_candidate_identity_v2(
    provider_id=PRIMARY, model_family="gpt-5.4", model_revision="gpt-5.4", deployment=None
)
ALTERNATE_CANONICAL = derive_candidate_identity_v2(
    provider_id=ALTERNATE,
    model_family="claude-sonnet-5",
    model_revision="claude-sonnet-5",
    deployment=None,
)


def test_derived_universe_matches_the_configured_pair() -> None:
    """Equivalence: under current configuration the derivation yields exactly
    the configured primary/fallback order with nothing excluded."""

    _ordered_fallback_settings()
    universe = derive_candidate_universe(resolve_provider_execution_config())

    assert universe.source is CandidateUniverseSource.CATALOGUE_DERIVED
    assert universe.candidate_entry_ids == [PRIMARY_CANONICAL, ALTERNATE_CANONICAL]
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

    assert universe.candidate_entry_ids == [ALTERNATE_CANONICAL]
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

    assert universe.candidate_entry_ids == [PRIMARY_CANONICAL]
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
                    # model_copy bypasses the stamping validator: an identity
                    # change must reset the canonical id so the write
                    # authority re-derives it (issue #314).
                    "candidate_id_v2": "",
                }
            )
        )

    _extra("gpt-5.5-preview", ModelLifecycleState.APPROVED)
    _extra("gpt-4.9-retired", ModelLifecycleState.RETIRED)

    universe = derive_candidate_universe(resolve_provider_execution_config())

    assert universe.candidate_entry_ids == [PRIMARY_CANONICAL, ALTERNATE_CANONICAL]
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
                "candidate_id_v2": "",
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
    assert decision.universe_source is CandidateUniverseSource.CATALOGUE_DERIVED
    assert [e.entry_id for e in decision.universe_exclusions] == [shadow_id]
    assert decision.universe_exclusions[0].reason is (
        CandidateUniverseExclusionReason.POLICY_EXCLUDED
    )


def test_excluded_identity_never_becomes_a_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The U2 flip: a lifecycle-ineligible primary is not enumerated and not
    attempted - the alternate serves alone, and the exclusion carries the
    reason where a candidate rejection used to."""

    _ordered_fallback_settings()
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    entry = repository.get_entry(PRIMARY_ENTRY)
    assert entry is not None
    repository.upsert_entry(
        entry.model_copy(update={"lifecycle_state": ModelLifecycleState.DEPRECATED})
    )
    adapter = _install_adapter(monkeypatch, failing={})

    from app.services.provider_gateway import execute_text_generation

    response = execute_text_generation(_request())

    assert response.provider_id == ALTERNATE
    assert adapter.executed_provider_ids == [ALTERNATE]
    decision = response.routing_decision
    assert decision is not None
    assert [c.provider_id for c in decision.candidates] == [ALTERNATE]
    assert [e.entry_id for e in decision.universe_exclusions] == [PRIMARY_ENTRY]
    assert decision.universe_exclusions[0].reason is (
        CandidateUniverseExclusionReason.LIFECYCLE_INELIGIBLE
    )
    # Evidence honesty: the configured primary did NOT serve - the selection
    # reason must describe the enumeration, never claim the primary served.
    assert "primary" not in decision.selection_reason
    assert "first candidate in the enumerated universe served" in decision.selection_reason


def test_empty_universe_refuses_with_every_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both policy-ordered identities excluded: no attempt happens, the
    refusal names the primary story, and the decision carries every reasoned
    exclusion with zero candidates."""

    from fastapi import HTTPException

    _ordered_fallback_settings()
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    for entry_id in (PRIMARY_ENTRY, ALTERNATE_ENTRY):
        entry = repository.get_entry(entry_id)
        assert entry is not None
        repository.upsert_entry(
            entry.model_copy(update={"lifecycle_state": ModelLifecycleState.RETIRED})
        )
    adapter = _install_adapter(monkeypatch, failing={})

    from app.services.provider_gateway import (
        ProviderGatewayUnavailableError,
        execute_text_generation,
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "MODEL_LIFECYCLE_INELIGIBLE" in str(exc_info.value.detail)
    assert adapter.executed_provider_ids == []
    assert isinstance(exc_info.value, ProviderGatewayUnavailableError)
    decision = exc_info.value.routing_decision
    assert decision.candidates == []
    assert decision.selected_provider_id is None
    assert "universe_exclusions" in decision.selection_reason
    assert sorted(e.entry_id for e in decision.universe_exclusions) == sorted(
        [PRIMARY_ENTRY, ALTERNATE_ENTRY]
    )
    assert all(
        e.reason is CandidateUniverseExclusionReason.LIFECYCLE_INELIGIBLE
        for e in decision.universe_exclusions
    )


def test_routing_posture_shows_the_universe_an_execution_would_get() -> None:
    """One derivation authority (issue #244, U3): the operator posture and the
    gateway read the same universe, so an identity excluded from posture is
    exactly the identity an execution would not enumerate."""

    from app.services.routing_posture import build_routing_posture

    _ordered_fallback_settings()
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    entry = repository.get_entry(PRIMARY_ENTRY)
    assert entry is not None
    repository.upsert_entry(
        entry.model_copy(update={"lifecycle_state": ModelLifecycleState.DEPRECATED})
    )

    posture = build_routing_posture()

    universe = posture.candidate_universe
    assert universe is not None
    assert universe.candidate_entry_ids == [ALTERNATE_CANONICAL]
    assert [e.entry_id for e in universe.exclusions] == [PRIMARY_ENTRY]
    assert universe.exclusions[0].reason is (CandidateUniverseExclusionReason.LIFECYCLE_INELIGIBLE)


def test_capability_posture_answers_who_is_eligible_and_who_would_serve() -> None:
    """Issue #244, S5: the posture runs the gateway's own eligibility check
    over the derived universe - eligible, excluded-with-reason, and the
    first-eligible selection, per queried capability."""

    from app.contracts.capability_requirements import CapabilityRequirements
    from app.services.routing_posture import build_routing_posture
    from tests.unit.test_ordered_fallback_routing import _assess_structured_output

    _ordered_fallback_settings()
    _assess_structured_output(PRIMARY, "gpt-5.4", True)

    posture = build_routing_posture(CapabilityRequirements(structured_output_required=True))

    capability = posture.capability_posture
    assert capability is not None
    assert [c.entry_id for c in capability.candidates] == [PRIMARY_CANONICAL, ALTERNATE_CANONICAL]
    assert capability.candidates[0].eligible is True
    assert capability.candidates[0].rejection_reason is None
    # The unassessed alternate fails closed AS unknown, never silently.
    assert capability.candidates[1].eligible is False
    assert capability.candidates[1].rejection_reason is (ProviderFailureCategory.CAPABILITY_UNKNOWN)
    assert capability.would_select_entry_id == PRIMARY_CANONICAL

    # Without a capability query there is no capability posture.
    assert build_routing_posture().capability_posture is None


def test_capability_posture_reflects_an_operator_degradation() -> None:
    """A degraded capability shows as CAPABILITY_DEGRADED on the posture with
    the operator's reason - "we turned this off" is visible, and selection
    moves (or empties) accordingly."""

    from app.contracts.capability_requirements import CapabilityRequirements
    from app.services.routing_posture import build_routing_posture
    from tests.unit.test_ordered_fallback_routing import _assess_structured_output

    _ordered_fallback_settings()
    _assess_structured_output(PRIMARY, "gpt-5.4", True)
    _assess_structured_output(ALTERNATE, "claude-sonnet-5", True)

    # The degradation control requires the durable store; write the overlay
    # directly for this read-model test.
    repository = get_model_catalogue_repository()
    entry = repository.get_entry(PRIMARY_ENTRY)
    assert entry is not None
    from app.contracts.model_catalogue import ModelCapabilityDegradation

    repository.upsert_entry(
        entry.model_copy(
            update={
                "capability_degradations": {
                    "supports_structured_output": ModelCapabilityDegradation(
                        dimension="supports_structured_output",
                        reason="Structured output failing contract validation.",
                        degraded_by="lotus-platform (credential ops-key-alpha)",
                        degraded_at="2026-09-03T12:00:00Z",
                    )
                }
            }
        )
    )

    posture = build_routing_posture(CapabilityRequirements(structured_output_required=True))

    capability = posture.capability_posture
    assert capability is not None
    assert capability.candidates[0].rejection_reason is (
        ProviderFailureCategory.CAPABILITY_DEGRADED
    )
    assert "failing contract validation" in str(capability.candidates[0].detail)
    assert capability.candidates[1].eligible is True
    assert capability.would_select_entry_id == ALTERNATE_CANONICAL
