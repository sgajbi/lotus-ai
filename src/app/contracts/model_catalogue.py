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

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.governed_actions import GovernedActionRecord


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

    KNOWN LIMITATION (issue #314): this is a delimiter-concatenated string and
    identity components may themselves contain the delimiter, so two distinct
    tuples can render identically (e.g. revision ``qwen3:8b`` with no
    deployment vs revision ``qwen3`` with deployment ``8b``). It remains the
    human-readable row key; the CANONICAL candidate identity is
    ``derive_candidate_identity_v2`` and the structured fields - never parse
    this string to recover identity components.
    """

    base = f"{provider_id}:{model_revision}"
    return f"{base}:{deployment}" if deployment else base


CANDIDATE_IDENTITY_V2_PREFIX = "cand2_"


def derive_candidate_identity_v2(
    *,
    provider_id: str,
    model_family: str,
    model_revision: str,
    deployment: str | None,
) -> str:
    """The canonical serving-candidate identity (issue #314): a versioned,
    opaque, deterministic identifier over the canonical serialization of the
    full immutable serving tuple.

    The canonical form is minified sorted-key JSON, so every component is
    unambiguously delimited regardless of its characters and a null
    deployment is distinct from every string. The digest makes the id
    collision-resistant and replay-stable; the ``cand2_`` prefix versions the
    scheme. Structured identity fields remain authoritative - semantics are
    NEVER reconstructed by parsing this id. Commercial SKU/rate-card
    identity is deliberately excluded: a different rate card is different
    commercial evidence, not a distinct independently routable candidate.
    """

    canonical = json.dumps(
        {
            "v": 2,
            "provider_id": provider_id,
            "model_family": model_family,
            "model_revision": model_revision,
            "deployment": deployment,
        },
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CANDIDATE_IDENTITY_V2_PREFIX}{digest}"


class ModelCapabilityDegradation(BaseModel):
    """One active operator capability degradation on a catalogue entry.

    An observed regression scoped to one capability dimension (issue #245,
    slice 2): the model stays in service for everything else, and the
    underlying assessed fact is never rewritten - the degradation overrides
    it only while present.
    """

    dimension: str = Field(min_length=1, description="Capability fact field degraded.")
    reason: str = Field(min_length=1, description="The observed regression.")
    degraded_by: str = Field(
        min_length=1, description="Verified identity that degraded the capability."
    )
    degraded_at: str = Field(description="Instant the degradation was recorded (UTC).")


class ModelCatalogueEntry(BaseModel):
    """One governed catalogue row for an exact model identity."""

    entry_id: str = Field(
        min_length=1,
        description=(
            "Human-readable row key derived from provider, revision and deployment. "
            "NOT the canonical identity - components may contain the delimiter, so "
            "never parse it; candidate_id_v2 and the structured fields are "
            "authoritative (issue #314)."
        ),
    )
    candidate_id_v2: str = Field(
        default="",
        description=(
            "Canonical serving-candidate identity (issue #314): versioned opaque "
            "deterministic digest of the (provider, family, revision, deployment) "
            "tuple. Stamped automatically from the structured fields; an explicit "
            "value that contradicts them is refused."
        ),
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
    capability_degradations: dict[str, ModelCapabilityDegradation] = Field(
        default_factory=dict,
        description=(
            "Active operator capability degradations keyed by capability fact field "
            "(issue #245, slice 2). While present, a degradation overrides the "
            "underlying fact for requirement routing; it never rewrites the fact. "
            "A cleared degradation is pinned inside the governed restore record."
        ),
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

    @model_validator(mode="after")
    def _stamp_canonical_candidate_identity(self) -> ModelCatalogueEntry:
        """Every entry carries its canonical identity, derived from the
        authoritative structured fields (issue #314). An absent value is
        stamped; an explicit value that contradicts the tuple is refused -
        the id can never drift from the identity it names."""

        derived = derive_candidate_identity_v2(
            provider_id=self.provider_id,
            model_family=self.model_family,
            model_revision=self.model_revision,
            deployment=self.deployment,
        )
        if not self.candidate_id_v2:
            self.candidate_id_v2 = derived
        elif self.candidate_id_v2 != derived:
            raise ValueError(
                "candidate_id_v2 must equal the canonical identity derived from the "
                f"structured serving tuple (expected '{derived}', got "
                f"'{self.candidate_id_v2}')"
            )
        return self


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

# Transitions INTO these states expand serving posture and are risk-increasing:
# they require the governed two-step flow (verified requester, distinct
# verified approver, PASS-verdict eval evidence) rather than the single-call
# transition route (issue #245). Every other target - taking a model out of
# service or moving it through evaluation - is a safety or administrative
# action one verified principal applies immediately.
MODEL_SERVING_PROMOTION_TARGETS: frozenset[ModelLifecycleState] = frozenset(
    {
        ModelLifecycleState.APPROVED,
        ModelLifecycleState.SHADOW,
        ModelLifecycleState.CANARY,
        ModelLifecycleState.PRODUCTION,
    }
)

# The capability dimensions requirement routing actually enforces (issue #245,
# slice 2): only these can be operator-degraded - degrading a dimension no
# routing decision consults would be a control that controls nothing.
DEGRADABLE_CAPABILITY_DIMENSIONS: frozenset[str] = frozenset(
    {"supports_structured_output", "supports_tool_calling"}
)

# States an operator has deliberately taken a model OUT of service through.
# Nothing automatic - including a seeding-authority change - may resurrect
# a model from these; only an explicit operator transition can.
OPERATOR_TERMINAL_LIFECYCLE_STATES = frozenset(
    {ModelLifecycleState.DEPRECATED, ModelLifecycleState.RETIRED}
)


class ServingPolicyVersionRecord(BaseModel):
    """One immutable version of the governed serving-policy artifact
    (issue #295, S2): the ordered identities that may serve, with the acting
    credentials recorded. Versions are append-only; the highest version is
    the operative policy."""

    version: int = Field(ge=1, description="Monotonic policy version; highest is operative.")
    ordered_entry_ids: list[str] = Field(
        description=(
            "Serving identities in governed order - order is policy, never ranking. "
            "Rows written since issue #314 store the CANONICAL candidate identity "
            "(cand2_...); historical rows keep the v1 row key they were reviewed "
            "under and are never rewritten - resolution accepts both, by exact key."
        )
    )
    action: Literal["IDENTITY_ADD", "IDENTITY_REMOVE"] = Field(
        description="What produced this version."
    )
    changed_entry_id: str = Field(min_length=1, description="The identity added or removed.")
    requested_by_key_id: str = Field(
        min_length=1, description="Verified credential that requested the change."
    )
    approver_key_id: str | None = Field(
        default=None,
        description=(
            "Distinct verified credential that approved an IDENTITY_ADD; null for "
            "IDENTITY_REMOVE, the risk-reducing safety direction taken by one "
            "verified principal immediately."
        ),
    )
    governed_action_id: str | None = Field(
        default=None,
        description="Governed-action evidence reference for two-step additions.",
    )
    recorded_at: str = Field(min_length=1)


class ModelLifecycleTransitionRecord(BaseModel):
    """One durable lifecycle transition on a catalogue entry."""

    event_id: str = Field(min_length=1, description="Server-assigned event identity.")
    entry_id: str = Field(min_length=1, description="Catalogue entry the transition applies to.")
    from_state: ModelLifecycleState = Field(description="State before the transition.")
    to_state: ModelLifecycleState = Field(description="State after the transition.")
    reason: str = Field(min_length=1, description="Operator reason recorded with the transition.")
    requested_by: str = Field(
        min_length=1,
        description="Verified identity that requested the transition (issue #245).",
    )
    approved_by: str | None = Field(
        default=None,
        description=(
            "Verified identity that approved a governed serving promotion; null for "
            "single-principal safety and administrative transitions, where no "
            "approval existed (issue #245)."
        ),
    )
    approval_evidence_ref: str | None = Field(
        default=None,
        description=(
            "Evidence reference recorded with a governed serving promotion "
            "(`evaluation-run:<run_id>`); null otherwise."
        ),
    )
    recorded_at: str = Field(description="Instant the transition was recorded (UTC).")


class ModelLifecycleTransitionRequest(BaseModel):
    """Single-principal safety or administrative transition.

    Caller identity comes from the authenticated credential, never from the
    body (issue #245). Serving promotions are refused here and go through the
    governed two-step promotion flow.
    """

    to_state: ModelLifecycleState = Field(description="Target lifecycle state.")
    reason: str = Field(min_length=1, description="Why this transition is being made.")


class ModelPromotionIntentRequest(BaseModel):
    """Step one of governed serving promotion: a verified requester states the intent.

    Eval evidence enables the decision; it does not make the decision - the
    named run must already exist with a PASS verdict, and a distinct verified
    credential still has to approve (issue #245).
    """

    to_state: ModelLifecycleState = Field(
        description="Serving target (APPROVED, SHADOW, CANARY or PRODUCTION)."
    )
    reason: str = Field(min_length=1, description="Why this promotion should happen.")
    evaluation_run_id: str = Field(
        min_length=1,
        description="Existing evaluation run whose PASS verdict backs this promotion.",
    )
    requested_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class ModelPromotionApprovalRequest(BaseModel):
    """Step two: a distinct verified credential approves the exact pending action."""

    action_id: str = Field(min_length=1, max_length=64, description="Pending governed action id.")
    action_hash: str = Field(
        min_length=64,
        max_length=64,
        description="Hash of the action being approved, exactly as returned by the request step.",
    )
    approved_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class ModelLifecycleTransitionResponse(BaseModel):
    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry: ModelCatalogueEntry = Field(description="The entry after the transition.")
    transition: ModelLifecycleTransitionRecord = Field(
        description="The durable transition record this action created.",
    )


class ModelCapabilityDegradationRequest(BaseModel):
    """Degrade one capability dimension on a catalogue entry.

    Safety direction: containing an observed regression is applied
    immediately by one verified principal - no approval step, and the caller
    identity comes from the authenticated credential (issue #245, slice 2).
    """

    dimension: str = Field(
        min_length=1,
        description="Capability fact field to degrade (e.g. supports_structured_output).",
    )
    reason: str = Field(min_length=1, description="The observed regression.")


class ModelCapabilityDegradationResponse(BaseModel):
    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry: ModelCatalogueEntry = Field(description="The entry after the degradation.")
    degradation: ModelCapabilityDegradation = Field(
        description="The degradation now active on the entry.",
    )


class ModelCapabilityRestoreIntentRequest(BaseModel):
    """Step one of governed capability restore: a verified requester states the intent.

    Clearing a degradation re-exposes the underlying evidence-derived fact to
    requirement routing - risk-increasing, so it takes a distinct verified
    approver and PASS-verdict eval evidence (issue #245, slice 2).
    """

    dimension: str = Field(min_length=1, description="Degraded capability fact field.")
    reason: str = Field(min_length=1, description="Why the regression is considered resolved.")
    evaluation_run_id: str = Field(
        min_length=1,
        description="Existing evaluation run whose PASS verdict backs this restore.",
    )
    requested_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class ModelCapabilityRestoreApprovalRequest(BaseModel):
    """Step two: a distinct verified credential approves the exact pending action."""

    action_id: str = Field(min_length=1, max_length=64, description="Pending governed action id.")
    action_hash: str = Field(
        min_length=64,
        max_length=64,
        description="Hash of the action being approved, exactly as returned by the request step.",
    )
    approved_by: str | None = Field(
        default=None,
        max_length=256,
        description="Claimed operator name; recorded as unverified attribution.",
    )


class ModelCapabilityRestoreApprovalResponse(BaseModel):
    """The executed capability restore with its full governance evidence chain."""

    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry: ModelCatalogueEntry = Field(description="The entry after the restore.")
    governed_action: GovernedActionRecord = Field(
        description=(
            "The request-approval-execution evidence chain; its payload pins the "
            "exact degradation that was cleared (issue #245, slice 2)."
        ),
    )
    summary: list[str] = Field(description="Human-readable account of what executed.")


class ModelPromotionApprovalResponse(BaseModel):
    """The executed serving promotion with its full governance evidence chain."""

    service: str = Field(description="Service name emitting the response.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where catalogue truth lives: memory or sqlalchemy.")
    entry: ModelCatalogueEntry = Field(description="The entry after the promotion.")
    transition: ModelLifecycleTransitionRecord = Field(
        description="The durable transition record this promotion created.",
    )
    governed_action: GovernedActionRecord = Field(
        description="The request-approval-execution evidence chain (issue #245).",
    )
    summary: list[str] = Field(description="Human-readable account of what executed.")


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


class ServingPolicyIdentityAddRequest(BaseModel):
    """Step one of adding an identity to the serving policy (issue #295, S2)."""

    entry_id: str = Field(min_length=1, description="Catalogue entry to add to the serving order.")
    reason: str = Field(min_length=1, description="Why this identity should be allowed to serve.")
    requested_by: str | None = Field(
        default=None, description="Optional human attribution alongside the verified credential."
    )


class ServingPolicyIdentityAddApprovalRequest(BaseModel):
    """Step two: a distinct verified credential approves the exact pending change."""

    action_id: str = Field(min_length=1)
    action_hash: str = Field(min_length=64, max_length=64)
    approved_by: str | None = Field(
        default=None, description="Optional human attribution alongside the verified credential."
    )


class ServingPolicyIdentityRemovalRequest(BaseModel):
    """Immediate risk-reducing removal by one verified principal (issue #295, S2)."""

    entry_id: str = Field(min_length=1, description="Catalogue entry to remove from serving order.")
    reason: str = Field(min_length=1, description="Why this identity must stop serving.")
    requested_by: str | None = Field(
        default=None, description="Optional human attribution alongside the verified identity."
    )


class ServingPolicyChangeResponse(BaseModel):
    service: str
    version: str
    policy: ServingPolicyVersionRecord = Field(description="The new operative policy version.")
    summary: list[str] = Field(default_factory=list)


class ServingPolicyStatusResponse(BaseModel):
    service: str
    version: str
    current: ServingPolicyVersionRecord | None = Field(
        default=None,
        description=(
            "The operative serving policy; null while ordering still comes from "
            "the configured primary/fallback pair."
        ),
    )
    versions: list[ServingPolicyVersionRecord] = Field(
        default_factory=list, description="Version history, newest first."
    )
    summary: list[str] = Field(default_factory=list)
