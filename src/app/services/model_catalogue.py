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

from app.config import settings
from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelCatalogueResponse,
    ModelCatalogueSeedReport,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import ProviderExecutionMode
from app.providers.configured_workflow_run_model_risk_inventory import (
    ConfiguredWorkflowRunModelRiskInventory,
)
from app.services.model_catalogue_store import get_model_catalogue_repository

_LIVE_TEXT_MODES = frozenset(
    {
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }
)

# Fields the seeder owns; created_at and last_updated_at carry row provenance
# and are managed by the idempotency logic, not compared as seed content.
_SEED_MANAGED_EXCLUDES = {"created_at", "last_updated_at"}


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

    if (
        settings.provider_mode in _LIVE_TEXT_MODES
        and settings.live_text_provider_id
        and settings.live_text_model_id
    ):
        revision_pinned = bool(settings.live_text_model_version)
        model_revision = settings.live_text_model_version or settings.live_text_model_id
        entry_id = derive_model_catalogue_entry_id(
            provider_id=settings.live_text_provider_id,
            model_revision=model_revision,
            deployment=None,
        )
        entries[entry_id] = ModelCatalogueEntry(
            entry_id=entry_id,
            provider_id=settings.live_text_provider_id,
            provider_mode=settings.provider_mode,
            model_family=settings.live_text_model_id,
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
            approved_workflow_pack_ids=list(approved.workflow_pack_ids),
            approval_evidence_refs=[approved.approval_ref],
            approved_from_utc=approved.approved_from_utc,
            approved_until_utc=approved.approved_until_utc,
            seed_source=ModelCatalogueSeedSource.APPROVED_WORKFLOW_RUN_MODEL_INVENTORY,
            created_at=now,
            last_updated_at=now,
        )

    return [entries[entry_id] for entry_id in sorted(entries)]


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
