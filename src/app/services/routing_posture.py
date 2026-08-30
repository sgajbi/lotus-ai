"""Operator routing-posture inspection (issue #176, slice 4).

Answers the charter's operator question - "which model is currently serving,
under which policy, and what would stop it" - by composing the surfaces that
already exist: the fixed routing policy identity, the single configured
candidate with its governed catalogue binding, the circuit-breaker status,
the enforcement flags, and the currently enforcing kill switches. Nothing here
re-derives eligibility logic; a posture read must never disagree with what the
gateway would actually do.

Policy-artifact versioning deliberately does not exist yet: there is one
policy (fixed_configured_mode v1) and its registry arrives with the second
policy (ordered_fallback, slice 3 of #176).
"""

from __future__ import annotations

from app.config import settings
from app.services.provider_execution_config import resolve_provider_execution_config
from app.contracts.model_catalogue import ModelCatalogueEntry, derive_model_catalogue_entry_id
from app.contracts.providers import (
    ROUTING_POLICY_FIXED_CONFIGURED_MODE,
    ROUTING_POLICY_VERSION_V1,
    RoutingPostureCandidateDescriptor,
    RoutingPostureResponse,
    RoutingStrategy,
)
from app.services.kill_switch_control import build_kill_switch_status
from app.services.model_catalogue import ensure_model_catalogue_seeded
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.provider_degradation_state import build_provider_degradation_status


def build_routing_posture() -> RoutingPostureResponse:
    config = resolve_provider_execution_config()
    candidate = _resolve_candidate()
    return RoutingPostureResponse(
        service=settings.service_name,
        version=settings.service_version,
        policy_id=ROUTING_POLICY_FIXED_CONFIGURED_MODE,
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.FIXED,
        candidate=candidate,
        degradation=build_provider_degradation_status(),
        quota_enforced=config.enforcement.quota_enforced,
        budget_enforced=config.enforcement.budget_enforced,
        enforcing_kill_switch_count=build_kill_switch_status().active_count,
        notes=[
            "The fixed policy maps the configured provider mode to exactly one adapter; "
            "this posture is the candidate the next live execution would bind.",
            "Per-request gates (caller authorization, task/tenant/caller kill-switch scopes, "
            "quota counters) are evaluated per execution and recorded on its routing decision.",
        ],
    )


def _resolve_candidate() -> RoutingPostureCandidateDescriptor:
    config = resolve_provider_execution_config()
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
