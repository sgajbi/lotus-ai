"""Governed model catalogue: seeding and the read model (issue #175, slice 1).

The catalogue is the single source of model identity. Slice 1 seeds it from the
two places model identity already lives - the live-text settings and the
approved workflow-run model-risk inventory - so the catalogue reflects reality
from its first read, and every seeded row is honest about how well-pinned that
reality is (`revision_pinned`). Later slices bind execution to catalogue rows,
add governed lifecycle transitions, and detect revision drift.

Seeding is idempotent and provenance-preserving: re-running it never duplicates
rows, never rewrites `created_at`, and touches `last_updated_at` only when a
seeded field actually changed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.model_catalogue import (
    OPERATOR_TERMINAL_LIFECYCLE_STATES,
    ModelCatalogueEntry,
    ModelCatalogueEntryDetailResponse,
    ModelCatalogueResponse,
    ModelCatalogueSeedReport,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    ModelRevisionDriftObservation,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import (
    CandidateUniverse,
    CandidateUniverseExclusionDescriptor,
    CandidateUniverseExclusionReason,
    CandidateUniverseSource,
    ProviderExecutionMode,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.providers.configured_workflow_run_model_risk_inventory import (
    ConfiguredWorkflowRunModelRiskInventory,
)
from app.contracts.capability_requirements import CapabilityRequirements
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.output_contracts import output_contract_exists
from app.services.provider_execution_config import (
    ProviderExecutionConfig,
    resolve_provider_execution_config,
)

_LIVE_TEXT_MODES = frozenset(
    {
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }
)

# Fields the seeder owns; created_at and last_updated_at carry row provenance
# and are managed by the idempotency logic, not compared as seed content.
_SEED_MANAGED_EXCLUDES = {"created_at", "last_updated_at"}

# A model in one of these states must not serve new executions. Reaching them
# requires an operator lifecycle transition (issue #175 slice 3); the fence is
# in place first so the transition has teeth from its first use.
_EXECUTION_INELIGIBLE_LIFECYCLE_STATES = frozenset(
    {
        ModelLifecycleState.DEGRADED,
        ModelLifecycleState.DEPRECATED,
        ModelLifecycleState.RETIRED,
    }
)


def upsert_model_catalogue_entry(entry: ModelCatalogueEntry) -> None:
    """Write one catalogue entry, enforcing the deterministic-identity guard."""

    expected_entry_id = derive_model_catalogue_entry_id(
        provider_id=entry.provider_id,
        model_revision=entry.model_revision,
        deployment=entry.deployment,
    )
    if entry.entry_id != expected_entry_id:
        raise ValueError(
            "model catalogue entry id must equal the identity derived from provider, "
            f"revision and deployment (expected '{expected_entry_id}', got '{entry.entry_id}')"
        )
    get_model_catalogue_repository().upsert_entry(entry)


def build_seed_model_catalogue_entries() -> list[ModelCatalogueEntry]:
    """Desired catalogue rows from the currently configured model identities.

    Two sources, in override order:

    1. The live-text settings, when a live text mode is configured with a
       provider and model - catalogued as CATALOGUED (configuration is not
       approval), with `revision_pinned` honest about whether an exact
       revision was configured.
    2. The approved workflow-run model-risk inventory - catalogued as
       APPROVED with the approval evidence attached. An inventory row for the
       same identity supersedes the settings row: approval is the stronger
       claim about the same model.
    """

    now = _utc_now_iso()
    entries: dict[str, ModelCatalogueEntry] = {}

    config = resolve_provider_execution_config()
    if config.provider_mode in _LIVE_TEXT_MODES and config.provider_id and config.model_id:
        revision_pinned = bool(config.model_version)
        model_revision = config.model_version or config.model_id
        entry_id = derive_model_catalogue_entry_id(
            provider_id=config.provider_id,
            model_revision=model_revision,
            deployment=None,
        )
        entries[entry_id] = ModelCatalogueEntry(
            entry_id=entry_id,
            provider_id=config.provider_id,
            provider_mode=config.provider_mode,
            model_family=config.model_id,
            model_revision=model_revision,
            deployment=None,
            sku=None,
            lifecycle_state=ModelLifecycleState.CATALOGUED,
            revision_pinned=revision_pinned,
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at=now,
            last_updated_at=now,
        )

    if (
        config.provider_mode in _LIVE_TEXT_MODES
        and config.fallback_provider_id
        and config.fallback_model_id
    ):
        # The configured alternate is a governed identity like the primary:
        # it seeds its own catalogue row and passes the same eligibility
        # fences at bind time (issue #176, S3).
        fallback_revision = config.fallback_model_version or config.fallback_model_id
        entry_id = derive_model_catalogue_entry_id(
            provider_id=config.fallback_provider_id,
            model_revision=fallback_revision,
            deployment=None,
        )
        entries[entry_id] = ModelCatalogueEntry(
            entry_id=entry_id,
            provider_id=config.fallback_provider_id,
            provider_mode=config.provider_mode,
            model_family=config.fallback_model_id,
            model_revision=fallback_revision,
            deployment=None,
            sku=None,
            lifecycle_state=ModelLifecycleState.CATALOGUED,
            revision_pinned=bool(config.fallback_model_version),
            modalities=["text"],
            seed_source=ModelCatalogueSeedSource.SETTINGS_LIVE_TEXT,
            created_at=now,
            last_updated_at=now,
        )

    inventory = ConfiguredWorkflowRunModelRiskInventory(settings=settings)
    for approved in inventory.approved_models():
        entry_id = derive_model_catalogue_entry_id(
            provider_id=approved.provider_id,
            model_revision=approved.model_version,
            deployment=None,
        )
        entries[entry_id] = ModelCatalogueEntry(
            entry_id=entry_id,
            provider_id=approved.provider_id,
            provider_mode=approved.provider_mode,
            model_family=approved.model_id,
            model_revision=approved.model_version,
            deployment=None,
            sku=None,
            lifecycle_state=ModelLifecycleState.APPROVED,
            revision_pinned=True,
            modalities=["text"],
            # No capability dimension is seeded: pack approval plus an output
            # contract proves effective structured output only for THAT pack's
            # governed scope, never the model-global claim a seeded fact would
            # make. The scoped evidence is consulted at eligibility time from
            # the fields that carry it (approved_workflow_pack_ids + the
            # execution's output-contract key); the model-global fact stays
            # unknown until an assessment actually proves it (issue #244).
            approved_workflow_pack_ids=list(approved.workflow_pack_ids),
            approval_evidence_refs=[approved.approval_ref],
            approved_from_utc=approved.approved_from_utc,
            approved_until_utc=approved.approved_until_utc,
            seed_source=ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY,
            created_at=now,
            last_updated_at=now,
        )

    return [entries[entry_id] for entry_id in sorted(entries)]


_CAPABILITY_DIMENSIONS = (
    "supports_structured_output",
    "supports_tool_calling",
    "supports_streaming",
    "context_window_tokens",
    "max_output_tokens",
)


def _preserve_assessed_capabilities(
    *, candidate: ModelCatalogueEntry, existing: ModelCatalogueEntry
) -> ModelCatalogueEntry:
    """Unknown never overwrites known (issue #244, S2).

    Null on a capability dimension means *not assessed*. A seed row that has
    no evidence for a dimension must not erase an assessment that already
    exists - reconciling the catalogue with configuration would otherwise
    quietly un-assess facts every startup. The seed may add facts it can
    prove; it may never subtract ones it cannot.
    """

    preserved: dict[str, object] = {
        dimension: getattr(existing, dimension)
        for dimension in _CAPABILITY_DIMENSIONS
        if getattr(candidate, dimension) is None and getattr(existing, dimension) is not None
    }
    # Operator degradations survive reseeding unconditionally: only the
    # governed restore flow may clear one (issue #245, slice 2).
    if existing.capability_degradations:
        preserved["capability_degradations"] = existing.capability_degradations
    return candidate.model_copy(update=preserved) if preserved else candidate


def ensure_model_catalogue_seeded() -> ModelCatalogueSeedReport:
    """Idempotently reconcile the store with the configured seed rows."""

    repository = get_model_catalogue_repository()
    created = updated = unchanged = 0
    for entry in build_seed_model_catalogue_entries():
        existing = repository.get_entry(entry.entry_id)
        if existing is None:
            upsert_model_catalogue_entry(entry)
            created += 1
            continue
        candidate = entry.model_copy(update={"created_at": existing.created_at})
        if (
            candidate.seed_source == existing.seed_source
            or existing.lifecycle_state in OPERATOR_TERMINAL_LIFECYCLE_STATES
        ):
            # Lifecycle state is governed, not configured: once a row exists,
            # the seed must never revert an operator transition (e.g. RETIRED
            # back to CATALOGUED). A change of seeding authority - the
            # inventory superseding a settings row - may re-assert lifecycle,
            # but never out of an operator-terminal state: a retired model
            # stays retired until an operator explicitly transitions it.
            candidate = candidate.model_copy(update={"lifecycle_state": existing.lifecycle_state})
        candidate = _preserve_assessed_capabilities(candidate=candidate, existing=existing)
        if candidate.model_dump(exclude=_SEED_MANAGED_EXCLUDES) == existing.model_dump(
            exclude=_SEED_MANAGED_EXCLUDES
        ):
            unchanged += 1
            continue
        upsert_model_catalogue_entry(candidate)
        updated += 1
    return ModelCatalogueSeedReport(
        created_count=created,
        updated_count=updated,
        unchanged_count=unchanged,
    )


# Requirement dimensions the routing decision enforces (issue #244, S3): the
# two catalogue-backed capability gates plus the latency ceiling, which is
# enforced by tightening the execution timeout before any candidate runs. The
# estimated-cost ceiling is declared-only until a pre-execution bound exists,
# and the routing decision says so.
ENFORCED_REQUIREMENT_DIMENSIONS = frozenset(
    {"structured_output_required", "tool_calling_required", "max_latency_ms"}
)

_CAPABILITY_FACT_BY_REQUIREMENT = {
    "structured_output_required": "supports_structured_output",
    "tool_calling_required": "supports_tool_calling",
}


def scoped_structured_output_evidence(
    entry: ModelCatalogueEntry, output_contract_key: str | None
) -> bool:
    """Effective Lotus structured-output evidence, exactly as broad as it is.

    The entry is approved for the governed scope being executed AND
    deterministic validation holds that scope's output to a strict-JSON
    contract. That proves the requirement for THIS scope only - it is never
    widened into a model-global capability claim (issue #244 correction:
    pack approval plus contract existence must not seed a global fact).
    """

    if not output_contract_key:
        return False
    return output_contract_key in entry.approved_workflow_pack_ids and output_contract_exists(
        output_contract_key
    )


def enforce_capability_requirements(
    *,
    requirements: CapabilityRequirements | None,
    entry: ModelCatalogueEntry,
    output_contract_key: str | None = None,
) -> None:
    """Reject a candidate whose catalogue entry cannot satisfy the workload.

    Unknown fails closed, and fails closed AS unknown: a fact the catalogue
    has never assessed refuses with CAPABILITY_UNKNOWN, distinctly from a
    fact it proves absent (CAPABILITY_NOT_SUPPORTED). Laundering unknown into
    a confident answer in either direction is how capability claims rot.

    Eligibility accepts evidence at either honest scope: an assessed
    model-global fact, or scoped effective evidence for exactly the governed
    scope this execution validates under. An operator degradation overrides
    both while present.
    """

    if requirements is None:
        return
    for requirement_field, fact_field in _CAPABILITY_FACT_BY_REQUIREMENT.items():
        if getattr(requirements, requirement_field) is not True:
            continue
        degradation = entry.capability_degradations.get(fact_field)
        if degradation is not None:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.CAPABILITY_DEGRADED,
                message=(
                    f"Candidate `{entry.entry_id}` has capability `{requirement_field}` "
                    f"degraded by an operator: {degradation.reason}"
                ),
            )
        fact = getattr(entry, fact_field)
        if fact is True:
            continue
        if fact is False:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.CAPABILITY_NOT_SUPPORTED,
                message=(
                    f"Candidate `{entry.entry_id}` does not support the required "
                    f"capability `{requirement_field}`."
                ),
            )
        if requirement_field == "structured_output_required" and scoped_structured_output_evidence(
            entry, output_contract_key
        ):
            continue
        raise ProviderExecutionError(
            category=ProviderFailureCategory.CAPABILITY_UNKNOWN,
            message=(
                f"Candidate `{entry.entry_id}` has no applicable evidence for the "
                f"required capability `{requirement_field}`"
                + (
                    f" in governed scope `{output_contract_key}`"
                    if requirement_field == "structured_output_required" and output_contract_key
                    else ""
                )
                + "; unknown is not eligibility."
            ),
        )


def derive_candidate_universe(config: ProviderExecutionConfig) -> CandidateUniverse:
    """Derive the ordered candidate universe from catalogue evidence bounded by policy.

    The policy bound is the configured primary/fallback identity order (issue
    #244); the catalogue supplies the evidence each identity must earn
    eligibility with. Every exclusion is reasoned: a policy identity with no
    catalogue entry, a policy identity whose lifecycle refuses service, and -
    the operator question configuration cannot answer - a serving-eligible
    catalogue entry for this mode that no policy row lets serve.

    Since U2 this derivation IS the ordered enumeration: an identity excluded
    here never becomes a candidate, and `source` records the flip on every
    routing decision.
    """

    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    policy_order: list[tuple[str | None, str | None, str | None]] = [
        (config.provider_id, config.model_id, config.model_version),
        (config.fallback_provider_id, config.fallback_model_id, config.fallback_model_version),
    ]

    candidate_entry_ids: list[str] = []
    exclusions: list[CandidateUniverseExclusionDescriptor] = []
    for provider_id, model_id, model_version in policy_order:
        if not provider_id or not model_id:
            continue
        entry_id = derive_model_catalogue_entry_id(
            provider_id=provider_id,
            model_revision=model_version or model_id,
            deployment=None,
        )
        entry = repository.get_entry(entry_id)
        if entry is None:
            exclusions.append(
                CandidateUniverseExclusionDescriptor(
                    entry_id=entry_id,
                    reason=CandidateUniverseExclusionReason.MODEL_NOT_CATALOGUED,
                    detail=(
                        f"Policy orders `{entry_id}` but no governed catalogue entry exists for it."
                    ),
                )
            )
            continue
        if entry.lifecycle_state in _EXECUTION_INELIGIBLE_LIFECYCLE_STATES:
            exclusions.append(
                CandidateUniverseExclusionDescriptor(
                    entry_id=entry_id,
                    reason=CandidateUniverseExclusionReason.LIFECYCLE_INELIGIBLE,
                    detail=(
                        f"`{entry_id}` is {entry.lifecycle_state.value} and not eligible "
                        "to serve new executions."
                    ),
                )
            )
            continue
        candidate_entry_ids.append(entry_id)

    policy_entry_ids = set(candidate_entry_ids) | {exclusion.entry_id for exclusion in exclusions}
    for entry in repository.list_entries():
        if entry.entry_id in policy_entry_ids:
            continue
        if entry.provider_mode != config.provider_mode:
            continue
        if entry.lifecycle_state in _EXECUTION_INELIGIBLE_LIFECYCLE_STATES:
            # Out of service by its own lifecycle, not by policy: reporting it
            # as policy-excluded would misattribute the reason.
            continue
        exclusions.append(
            CandidateUniverseExclusionDescriptor(
                entry_id=entry.entry_id,
                reason=CandidateUniverseExclusionReason.POLICY_EXCLUDED,
                detail=(
                    f"`{entry.entry_id}` is serving-eligible for mode "
                    f"`{config.provider_mode}` but no policy row lets it serve."
                ),
            )
        )

    return CandidateUniverse(
        source=CandidateUniverseSource.CATALOGUE_DERIVED,
        candidate_entry_ids=candidate_entry_ids,
        exclusions=exclusions,
    )


def bind_live_text_model_catalogue_entry() -> ModelCatalogueEntry:
    """Resolve the catalogue entry for the configured live-text identity, fail-closed.

    Called on the live execution path: the returned entry is the governed
    identity this execution runs under. No entry, or an entry in an
    execution-ineligible lifecycle state, refuses execution with a bounded
    failure category rather than falling back to raw settings strings.
    """

    ensure_model_catalogue_seeded()
    config = resolve_provider_execution_config()
    provider_id = config.provider_id
    model_id = config.model_id
    if not provider_id or not model_id:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.MODEL_NOT_CATALOGUED,
            message="Live text execution requires a configured provider and model identity.",
        )
    model_revision = config.model_version or model_id
    entry_id = derive_model_catalogue_entry_id(
        provider_id=provider_id,
        model_revision=model_revision,
        deployment=None,
    )
    entry = get_model_catalogue_repository().get_entry(entry_id)
    if entry is None:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.MODEL_NOT_CATALOGUED,
            message=f"No governed model-catalogue entry exists for '{entry_id}'.",
        )
    if entry.lifecycle_state in _EXECUTION_INELIGIBLE_LIFECYCLE_STATES:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.MODEL_LIFECYCLE_INELIGIBLE,
            message=(
                f"Model-catalogue entry '{entry_id}' is {entry.lifecycle_state.value} "
                "and not eligible to serve new executions."
            ),
        )
    return entry


def build_model_catalogue_entry_detail(entry_id: str) -> ModelCatalogueEntryDetailResponse:
    ensure_model_catalogue_seeded()
    repository = get_model_catalogue_repository()
    entry = repository.get_entry(entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No model-catalogue entry exists for `{entry_id}`.",
        )
    return ModelCatalogueEntryDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.model_catalogue_store_mode,
        entry=entry,
        lifecycle_events=repository.list_lifecycle_events(entry_id),
        revision_drift_observations=repository.list_drift_observations(entry_id),
    )


def record_model_revision_drift(
    *,
    entry: ModelCatalogueEntry,
    observed_model_id: str | None,
) -> None:
    """Record that a provider served an identity other than the expectation.

    Called by the gateway after every live execution with the bound entry and
    the provider's echoed model id. An echo equal to the pinned revision or to
    the family identity is agreement, not drift. Observations are deduplicated
    per (entry, observed id): repetition updates last_observed_at and count.
    """

    if not observed_model_id:
        return
    if observed_model_id in {entry.model_revision, entry.model_family}:
        return
    observation_id = f"{entry.entry_id}::{observed_model_id}"
    repository = get_model_catalogue_repository()
    existing = repository.get_drift_observation(observation_id)
    now = _utc_now_iso()
    if existing is None:
        repository.upsert_drift_observation(
            ModelRevisionDriftObservation(
                observation_id=observation_id,
                entry_id=entry.entry_id,
                expected_identity=entry.model_revision,
                observed_model_id=observed_model_id,
                revision_pinned_at_observation=entry.revision_pinned,
                first_observed_at=now,
                last_observed_at=now,
                observation_count=1,
            )
        )
        return
    repository.upsert_drift_observation(
        existing.model_copy(
            update={
                "last_observed_at": now,
                "observation_count": existing.observation_count + 1,
            }
        )
    )


def build_model_catalogue_response() -> ModelCatalogueResponse:
    ensure_model_catalogue_seeded()
    entries = get_model_catalogue_repository().list_entries()
    return ModelCatalogueResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.model_catalogue_store_mode,
        entry_count=len(entries),
        unpinned_revision_count=sum(1 for entry in entries if not entry.revision_pinned),
        entries=entries,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
