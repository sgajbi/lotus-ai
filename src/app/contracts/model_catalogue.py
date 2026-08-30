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


# Governed lifecycle transitions (issue #175, slice 3). The edge table is the
# policy: every reachable state change is an explicit operator action with a
# recorded reason, and promotion to APPROVED must carry approval evidence.
ALLOWED_MODEL_LIFECYCLE_TRANSITIONS: dict[ModelLifecycleState, frozenset[ModelLifecycleState]] = {
    ModelLifecycleState.DISCOVERED: frozenset({ModelLifecycleState.CATALOGUED}),
    ModelLifecycleState.CATALOGUED: frozenset(
        {ModelLifecycleState.EVALUATING, ModelLifecycleState.DEPRECATED}
    ),
    ModelLifecycleState.EVALUATING: frozenset(
        {
            ModelLifecycleState.APPROVED,
            ModelLifecycleState.CATALOGUED,
            ModelLifecycleState.DEPRECATED,
        }
    ),
    ModelLifecycleState.APPROVED: frozenset(
        {
            ModelLifecycleState.SHADOW,
            ModelLifecycleState.CANARY,
            ModelLifecycleState.PRODUCTION,
            ModelLifecycleState.DEGRADED,
            ModelLifecycleState.DEPRECATED,
        }
    ),
    ModelLifecycleState.SHADOW: frozenset(
        {
            ModelLifecycleState.CANARY,
            ModelLifecycleState.APPROVED,
            ModelLifecycleState.DEPRECATED,
        }
    ),
    ModelLifecycleState.CANARY: frozenset(
        {
            ModelLifecycleState.PRODUCTION,
            ModelLifecycleState.APPROVED,
            ModelLifecycleState.DEGRADED,
            ModelLifecycleState.DEPRECATED,
        }
    ),
    ModelLifecycleState.PRODUCTION: frozenset(
        {ModelLifecycleState.DEGRADED, ModelLifecycleState.DEPRECATED}
    ),
    ModelLifecycleState.DEGRADED: frozenset(
        {
            ModelLifecycleState.PRODUCTION,
            ModelLifecycleState.CANARY,
            ModelLifecycleState.DEPRECATED,
        }
    ),
    ModelLifecycleState.DEPRECATED: frozenset({ModelLifecycleState.RETIRED}),
    ModelLifecycleState.RETIRED: frozenset(),
}

# States an operator has deliberately taken a model OUT of service through.
# Nothing automatic - including a seeding-authority change - may resurrect
# a model from these; only an explicit operator transition can.
OPERATOR_TERMINAL_LIFECYCLE_STATES = frozenset(
    {ModelLifecycleState.DEPRECATED, ModelLifecycleState.RETIRED}
)


class ModelLifecycleTransitionRecord(BaseModel):
    """One durable lifecycle transition on a catalogue entry."""

    event_id: str = Field(min_length=1, description="Server-assigned event identity.")
    entry_id: str = Field(min_length=1, description="Catalogue entry the transition applies to.")
    from_state: ModelLifecycleState = Field(description="State before the transition.")
    to_state: ModelLifecycleState = Field(description="State after the transition.")
    reason: str = Field(min_length=1, description="Operator reason recorded with the transition.")
    requested_by: str = Field(min_length=1, description="Operator who requested the transition.")
    approved_by: str = Field(min_length=1, description="Operator who approved the transition.")
    approval_evidence_ref: str | None = Field(
        default=None,
        description="Approval evidence reference; required when transitioning to APPROVED.",
    )
    recorded_at: str = Field(description="Instant the transition was recorded (UTC).")


class ModelLifecycleTransitionRequest(BaseModel):
    caller_app: str = Field(min_length=1, description="Calling application identity.")
    to_state: ModelLifecycleState = Field(description="Target lifecycle state.")
    reason: str = Field(min_length=1, description="Why this transition is being made.")
    requested_by: str = Field(min_length=1, description="Operator requesting the transition.")
    approved_by: str = Field(min_length=1, description="Operator approving the transition.")
    approval_evidence_ref: str | None = Field(
        default=None,
        description="Approval evidence reference; required when to_state is APPROVED.",
    )


class ModelLifecycleTransitionResponse(BaseModel):
    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry: ModelCatalogueEntry = Field(description="The entry after the transition.")
    transition: ModelLifecycleTransitionRecord = Field(
        description="The durable transition record this action created.",
    )


class ModelCatalogueEntryDetailResponse(BaseModel):
    """One catalogue entry with its full lifecycle history."""

    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry: ModelCatalogueEntry = Field(description="The catalogue entry.")
    lifecycle_events: list[ModelLifecycleTransitionRecord] = Field(
        description="Every recorded lifecycle transition for this entry, newest first.",
    )
    revision_drift_observations: list[ModelRevisionDriftObservation] = Field(
        description=(
            "Deduplicated observations of the provider serving a model identity other than "
            "this entry's expectation, most recently observed first."
        ),
    )


class ModelRevisionDriftObservation(BaseModel):
    """One deduplicated observation that a provider served a model identity
    other than the catalogue expectation (issue #175, slice 4).

    Observations are keyed by (entry, observed identifier): repeated identical
    drift updates last_observed_at and the count instead of flooding the store.
    """

    observation_id: str = Field(min_length=1, description="Deterministic observation identity.")
    entry_id: str = Field(min_length=1, description="Catalogue entry the execution was bound to.")
    expected_identity: str = Field(
        min_length=1,
        description="What the catalogue expected: the pinned revision, or the family identity.",
    )
    observed_model_id: str = Field(
        min_length=1,
        description="Model identifier the provider actually echoed for the execution.",
    )
    revision_pinned_at_observation: bool = Field(
        description="Whether the entry pinned an exact revision when this drift was observed.",
    )
    first_observed_at: str = Field(description="First instant this drift was observed (UTC).")
    last_observed_at: str = Field(description="Most recent instant this drift was observed (UTC).")
    observation_count: int = Field(ge=1, description="How many executions observed this drift.")
