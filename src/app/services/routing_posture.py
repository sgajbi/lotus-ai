"""Operator routing-posture inspection (issue #176, slices 3-4).

Answers the charter's operator question - "which model is currently serving,
under which policy, and what would stop it" - by composing the surfaces that
already exist: the configured routing policy identity, the candidate(s) with
their governed catalogue bindings, the per-candidate circuit-breaker status,
the enforcement flags, and the currently enforcing kill switches. Nothing here
re-derives eligibility logic; a posture read must never disagree with what the
gateway would actually do.
"""

from __future__ import annotations

from app.config import settings
from app.services.provider_execution_config import (
    ProviderExecutionConfig,
    derive_fallback_execution_config,
    resolve_provider_execution_config,
)
from app.contracts.model_catalogue import ModelCatalogueEntry, derive_model_catalogue_entry_id
from app.contracts.providers import (
    ROUTING_POLICY_FIXED_CONFIGURED_MODE,
    ROUTING_POLICY_ORDERED_FALLBACK,
    ROUTING_POLICY_VERSION_V1,
    ProviderDegradationStatusDescriptor,
    RoutingPostureCandidateDescriptor,
    RoutingPostureResponse,
    RoutingStrategy,
)
from app.services.kill_switch_control import build_kill_switch_status
from app.services.model_catalogue import (
    derive_candidate_universe,
    ensure_model_catalogue_seeded,
)
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.provider_degradation_state import build_provider_degradation_status


def build_routing_posture() -> RoutingPostureResponse:
    config = resolve_provider_execution_config()
    ordered = config.routing_strategy == "ordered_fallback"
    alternate = derive_fallback_execution_config(config) if ordered else None
    fallback_candidate: RoutingPostureCandidateDescriptor | None = None
    fallback_degradation: ProviderDegradationStatusDescriptor | None = None
    if alternate is not None:
        # Both reads name the alternate explicitly rather than relying on an
        # ambient override to mean it. Scope-implicit identity is how the
        # alternate's evidence used to come back describing the primary
        # (issue #237).
        fallback_candidate = _resolve_candidate(alternate)
        fallback_degradation = build_provider_degradation_status(alternate.provider_id)
    notes = [
        "Per-request gates (caller authorization, task/tenant/caller kill-switch scopes, "
        "quota counters) are evaluated per execution and recorded on its routing decision.",
    ]
    if ordered:
        notes.insert(
            0,
            "The ordered-fallback policy attempts the primary candidate first; a transient "
            "provider failure or candidate-scoped rejection routes to the alternate, and "
            "each candidate's breaker is keyed to its own provider identity.",
        )
    else:
        notes.insert(
            0,
            "The fixed policy maps the configured provider mode to exactly one adapter; "
            "this posture is the candidate the next live execution would bind.",
        )
    return RoutingPostureResponse(
        service=settings.service_name,
        version=settings.service_version,
        policy_id=(
            ROUTING_POLICY_ORDERED_FALLBACK if ordered else ROUTING_POLICY_FIXED_CONFIGURED_MODE
        ),
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.ORDERED_FALLBACK if ordered else RoutingStrategy.FIXED,
        candidate=_resolve_candidate(config),
        degradation=build_provider_degradation_status(),
        fallback_candidate=fallback_candidate,
        fallback_degradation=fallback_degradation,
        quota_enforced=config.enforcement.quota_enforced,
        budget_enforced=config.enforcement.budget_enforced,
        enforcing_kill_switch_count=build_kill_switch_status().active_count,
        # The same derivation the gateway enumerates from (issue #244, U3):
        # one authority, so the posture cannot disagree with routing.
        candidate_universe=derive_candidate_universe(config) if ordered else None,
        notes=notes,
    )


def _resolve_candidate(config: ProviderExecutionConfig) -> RoutingPostureCandidateDescriptor:
    provider_id = config.provider_id
    model_id = config.model_id
    entry: ModelCatalogueEntry | None = None
    if provider_id and model_id:
        ensure_model_catalogue_seeded()
        entry_id = derive_model_catalogue_entry_id(
            provider_id=provider_id,
            model_revision=config.model_version or model_id,
            deployment=None,
        )
        entry = get_model_catalogue_repository().get_entry(entry_id)
    return RoutingPostureCandidateDescriptor(
        provider_id=provider_id,
        provider_mode=config.provider_mode,
        model_catalogue_entry_id=entry.entry_id if entry is not None else None,
        model_family=entry.model_family if entry is not None else None,
        model_revision=entry.model_revision if entry is not None else None,
        revision_pinned=entry.revision_pinned if entry is not None else None,
        lifecycle_state=entry.lifecycle_state.value if entry is not None else None,
    )
