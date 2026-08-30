"""Model identity and governed model-catalogue contracts (issue #175, slice 1).

The catalogue is the governed source of model identity for lotus-ai. Identity is
deliberately multi-dimensional - provider, family, exact revision, deployment and
commercial SKU are separate fields, never one collapsed string - so that model
fungibility duties (pinning, substitution, drift detection, lifecycle governance)
have a first-class object to attach to.

Slice 1 introduces the vocabulary, the entry shape and the seeded read model.
Lifecycle transitions, execution binding and drift detection are later slices of
issue #175; the states are declared here in full so records never need a
vocabulary migration when those slices land.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ModelLifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    CATALOGUED = "CATALOGUED"
    EVALUATING = "EVALUATING"
    APPROVED = "APPROVED"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    PRODUCTION = "PRODUCTION"
    DEGRADED = "DEGRADED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class ModelCatalogueSeedSource(str, Enum):
    SETTINGS_LIVE_TEXT = "settings_live_text"
    APPROVED_WORKFLOW_RUN_MODEL_INVENTORY = "approved_workflow_run_model_inventory"
    OPERATOR = "operator"


def derive_model_catalogue_entry_id(
    *,
    provider_id: str,
    model_revision: str,
    deployment: str | None,
) -> str:
    """Deterministic entry identity for one (provider, revision, deployment).

    The derivation is the duplicate guard: the same identity triple always maps
    to the same entry id, so a second write for the triple is an upsert of the
    existing row rather than a silent sibling.
    """

    base = f"{provider_id}:{model_revision}"
    return f"{base}:{deployment}" if deployment else base


class ModelCatalogueEntry(BaseModel):
    """One governed catalogue row for an exact model identity."""

    entry_id: str = Field(
        min_length=1,
        description="Deterministic identity derived from provider, revision and deployment.",
    )
    provider_id: str = Field(
        min_length=1,
        description="Provider identity that serves this model (e.g. text.openai, text.local).",
    )
    provider_mode: str = Field(
        min_length=1,
        description="Provider execution mode this entry serves (a ProviderExecutionMode value).",
    )
    model_family: str = Field(
        min_length=1,
        description="Model family or product line identifier, distinct from the exact revision.",
    )
    model_revision: str = Field(
        min_length=1,
        description=(
            "Exact model revision when pinned; the family/tag identifier fallback otherwise "
            "(see revision_pinned)."
        ),
    )
    deployment: str | None = Field(
        default=None,
        description="Hosting deployment identity where applicable; null for direct provider APIs.",
    )
    sku: str | None = Field(
        default=None,
        description="Commercial SKU identity where known; null until priced (issue #178).",
    )
    lifecycle_state: ModelLifecycleState = Field(
        description="Governed lifecycle state of this model identity.",
    )
    revision_pinned: bool = Field(
        description=(
            "True when model_revision is an explicitly configured exact revision; False when it "
            "fell back to the family/tag identifier and is therefore drift-exposed."
        ),
    )
    modalities: list[str] = Field(
        default_factory=list,
        description="Declared modalities (e.g. text, embeddings); empty until assessed.",
    )
    context_window_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Declared context-window limit in tokens; null until assessed.",
    )
    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Declared output-token limit; null until assessed.",
    )
    supports_structured_output: bool | None = Field(
        default=None,
        description="Structured-output capability; null means not yet assessed.",
    )
    supports_tool_calling: bool | None = Field(
        default=None,
        description="Tool/function-calling capability; null means not yet assessed.",
    )
    supports_streaming: bool | None = Field(
        default=None,
        description="Streaming capability; null means not yet assessed.",
    )
    approved_workflow_pack_ids: list[str] = Field(
        default_factory=list,
        description="Workflow packs this identity is approved for, from the model-risk inventory.",
    )
    approval_evidence_refs: list[str] = Field(
        default_factory=list,
        description="Approval evidence references (e.g. model-risk approval refs).",
    )
    approved_from_utc: str | None = Field(
        default=None,
        description="Approval validity start (UTC) where an approval exists.",
    )
    approved_until_utc: str | None = Field(
        default=None,
        description="Approval validity end (UTC); null means no recorded expiry.",
    )
    seed_source: ModelCatalogueSeedSource = Field(
        description="Provenance of this row: settings seed, approved inventory seed, or operator.",
    )
    created_at: str = Field(description="Instant this entry was first catalogued (UTC).")
    last_updated_at: str = Field(description="Instant this entry last changed (UTC).")


class ModelCatalogueSeedReport(BaseModel):
    """Outcome of one idempotent seeding pass."""

    created_count: int = Field(ge=0, description="Entries created by this pass.")
    updated_count: int = Field(ge=0, description="Existing entries whose seeded fields changed.")
    unchanged_count: int = Field(ge=0, description="Entries already up to date.")


class ModelCatalogueResponse(BaseModel):
    """The governed model catalogue as currently stored."""

    service: str = Field(description="Service name emitting the model catalogue.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry_count: int = Field(ge=0, description="Number of catalogue entries.")
    unpinned_revision_count: int = Field(
        ge=0,
        description=(
            "Entries whose revision fell back to a family/tag identifier - drift-exposed "
            "until an exact revision is pinned."
        ),
    )
    entries: list[ModelCatalogueEntry] = Field(
        description="Catalogue entries ordered by entry id.",
    )
