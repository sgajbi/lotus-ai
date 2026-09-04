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

from urllib.parse import urlsplit

from app.config import settings
from app.services.provider_connection_material import configured_connection_materials
from app.services.provider_execution_config import (
    ProviderExecutionConfig,
    derive_fallback_execution_config,
    resolve_provider_execution_config,
)
from app.contracts.capability_requirements import CapabilityRequirements
from app.contracts.model_catalogue import ModelCatalogueEntry, derive_model_catalogue_entry_id
from app.contracts.providers import (
    ROUTING_POLICY_FIXED_CONFIGURED_MODE,
    ROUTING_POLICY_ORDERED_FALLBACK,
    ROUTING_POLICY_VERSION_V1,
    CandidateUniverse,
    ProviderDegradationStatusDescriptor,
    ProviderFailureCategory,
    RoutingStrategy,
)
from app.contracts.provider_routing_posture import (
    CapabilityPostureCandidateDescriptor,
    CapabilityPostureDescriptor,
    ConnectionIdentityDescriptor,
    RoutingPostureCandidateDescriptor,
    RoutingPostureResponse,
)
from app.providers.base import ProviderExecutionError
from app.services.kill_switch_control import build_kill_switch_status
from app.services.model_catalogue import (
    derive_candidate_universe,
    enforce_capability_requirements,
    ensure_model_catalogue_seeded,
)
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.provider_degradation_state import build_provider_degradation_status


def build_routing_posture(
    requirements: CapabilityRequirements | None = None,
    output_contract_key: str | None = None,
) -> RoutingPostureResponse:
    config = resolve_provider_execution_config()
    ordered = config.routing_strategy == "ordered_fallback"
    alternate = derive_fallback_execution_config(config) if ordered else None
    universe = derive_candidate_universe(config) if ordered else None
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
        candidate_universe=universe,
        capability_posture=(
            _build_capability_posture(
                universe=universe,
                requirements=requirements,
                output_contract_key=output_contract_key,
            )
            if universe is not None and requirements is not None
            else None
        ),
        connection_identities=_build_connection_identities(config),
        notes=notes,
    )


def _build_connection_identities(
    config: ProviderExecutionConfig,
) -> list[ConnectionIdentityDescriptor]:
    """Per-identity connection facts from the ONE merged material map (issues
    #298, #303): the same resolution execution consumes, so the operator
    answer to "which deployment/region/credential actually serves identity
    X" can never disagree with the call that serves it."""

    try:
        materials = configured_connection_materials(config)
    except ValueError:
        # Malformed declared material is a startup finding and refuses live
        # execution fail-closed; the posture read stays available and simply
        # cannot enumerate identities it cannot resolve.
        return []
    return [
        ConnectionIdentityDescriptor(
            entry_id=material.entry_id,
            provider_id=material.provider_id,
            model_revision=material.model_version or material.model_id,
            deployment=material.deployment,
            region=material.region,
            endpoint_host=urlsplit(material.api_base).netloc or None,
            credential_env=material.api_key_env,
            seeded=material.seeded,
        )
        for material in materials.values()
    ]


def _build_capability_posture(
    *,
    universe: CandidateUniverse,
    requirements: CapabilityRequirements,
    output_contract_key: str | None = None,
) -> CapabilityPostureDescriptor:
    """Per-candidate capability eligibility, with the gateway's own check.

    Runs `enforce_capability_requirements` - not a re-derivation of its logic -
    over the exact universe the next execution would enumerate, so "who is
    eligible for capability X" can never disagree with what routing enforces
    (issue #244, S5). Without a governed scope the answer is the model-global
    question (honest UNKNOWN unless assessed); with `output_contract_key` it
    is the scoped question an execution of that contract would get, and the
    eligible verdict names which evidence made it so.
    """

    repository = get_model_catalogue_repository()
    candidates: list[CapabilityPostureCandidateDescriptor] = []
    would_select: str | None = None
    for entry_id in universe.candidate_entry_ids:
        entry = repository.get_entry(entry_id)
        if entry is None:
            # The universe was derived moments ago; a vanished entry is a
            # concurrent catalogue change - report it as not catalogued.
            candidates.append(
                CapabilityPostureCandidateDescriptor(
                    entry_id=entry_id,
                    eligible=False,
                    rejection_reason=ProviderFailureCategory.MODEL_NOT_CATALOGUED,
                    detail=f"`{entry_id}` is no longer catalogued.",
                )
            )
            continue
        try:
            enforce_capability_requirements(
                requirements=requirements,
                entry=entry,
                output_contract_key=output_contract_key,
            )
        except ProviderExecutionError as exc:
            candidates.append(
                CapabilityPostureCandidateDescriptor(
                    entry_id=entry_id,
                    eligible=False,
                    rejection_reason=exc.category,
                    detail=exc.message,
                )
            )
            continue
        # Name the evidence that made the verdict, at its honest scope.
        if requirements.structured_output_required is True and (
            entry.supports_structured_output is not True
        ):
            basis = (
                "effective Lotus structured-output evidence scoped to output contract "
                f"`{output_contract_key}`"
            )
        else:
            basis = "assessed model-global capability facts"
        candidates.append(
            CapabilityPostureCandidateDescriptor(entry_id=entry_id, eligible=True, detail=basis)
        )
        if would_select is None:
            would_select = entry_id
    return CapabilityPostureDescriptor(
        requirements=requirements,
        candidates=candidates,
        would_select_entry_id=would_select,
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
            deployment=config.deployment,
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
