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
from typing import cast
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionType,
)
from app.contracts.model_catalogue import (
    ALLOWED_MODEL_LIFECYCLE_TRANSITIONS,
    DEGRADABLE_CAPABILITY_DIMENSIONS,
    MODEL_SERVING_PROMOTION_TARGETS,
    OPERATOR_TERMINAL_LIFECYCLE_STATES,
    ModelCapabilityDegradation,
    ModelCapabilityDegradationRequest,
    ModelCapabilityDegradationResponse,
    ModelCapabilityRestoreApprovalRequest,
    ModelCapabilityRestoreApprovalResponse,
    ModelCapabilityRestoreIntentRequest,
    ModelCatalogueEntry,
    ModelCatalogueEntryDetailResponse,
    ModelCatalogueResponse,
    ModelCatalogueSeedReport,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    ModelLifecycleTransitionRecord,
    ModelLifecycleTransitionRequest,
    ModelLifecycleTransitionResponse,
    ModelPromotionApprovalRequest,
    ModelPromotionApprovalResponse,
    ModelPromotionIntentRequest,
    ModelRevisionDriftObservation,
    derive_model_catalogue_entry_id,
)
from app.contracts.providers import ProviderExecutionMode, ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.providers.configured_workflow_run_model_risk_inventory import (
    ConfiguredWorkflowRunModelRiskInventory,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request, require_authorized
from app.contracts.capability_requirements import CapabilityRequirements
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.kill_switch_control import verified_caller_identity
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.output_contracts import output_contract_exists
from app.services.provider_execution_config import resolve_provider_execution_config

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
            # Provable from the approval evidence itself (issue #244, S2): a
            # pack-approved model has produced output that the deterministic
            # validator held to the pack's strict-JSON schema contract. No
            # other capability dimension has in-repo evidence, so no other
            # dimension is seeded - unknown stays unknown, and configuration
            # alone (the settings rows above) proves nothing.
            supports_structured_output=(
                True
                if any(output_contract_exists(pack_id) for pack_id in approved.workflow_pack_ids)
                else None
            ),
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


def enforce_capability_requirements(
    *,
    requirements: CapabilityRequirements | None,
    entry: ModelCatalogueEntry,
) -> None:
    """Reject a candidate whose catalogue entry cannot satisfy the workload.

    Unknown fails closed, and fails closed AS unknown: a fact the catalogue
    has never assessed refuses with CAPABILITY_UNKNOWN, distinctly from a
    fact it proves absent (CAPABILITY_NOT_SUPPORTED). Laundering unknown into
    a confident answer in either direction is how capability claims rot.
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
        raise ProviderExecutionError(
            category=ProviderFailureCategory.CAPABILITY_UNKNOWN,
            message=(
                f"Candidate `{entry.entry_id}` has no assessed catalogue fact for the "
                f"required capability `{requirement_field}`; unknown is not eligibility."
            ),
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


def _require_provider_control_authorization(caller: AuthenticatedCaller) -> None:
    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )


def _require_durable_catalogue_store() -> None:
    if settings.model_catalogue_store_mode != "sqlalchemy":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Model lifecycle transitions require LOTUS_AI_MODEL_CATALOGUE_STORE_MODE="
                "sqlalchemy so governed state changes survive restarts."
            ),
        )


def _get_required_catalogue_entry(entry_id: str) -> ModelCatalogueEntry:
    entry = get_model_catalogue_repository().get_entry(entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No model-catalogue entry exists for `{entry_id}`.",
        )
    return entry


def _validate_lifecycle_edge(entry: ModelCatalogueEntry, to_state: ModelLifecycleState) -> None:
    allowed = ALLOWED_MODEL_LIFECYCLE_TRANSITIONS[entry.lifecycle_state]
    if to_state not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Transition {entry.lifecycle_state.value} -> {to_state.value} is not "
                f"allowed; permitted targets: "
                f"{sorted(state.value for state in allowed) or 'none (terminal state)'}."
            ),
        )


def _require_pass_verdict_evaluation_run(run_id: str) -> None:
    """Promotion evidence must name a real, completed, PASS-verdict eval run.

    Eval evidence enables the decision; it does not make the decision - but a
    pending approval must never be parked on, or execute against, evidence
    that does not exist or did not actually pass (issue #245).
    """

    run = get_evaluation_runtime_store().get_run(run_id=run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Evaluation run `{run_id}` does not exist; promotion evidence must name "
                "a real evaluation run."
            ),
        )
    if run.lifecycle_status != "COMPLETED" or run.verdict != "PASS":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Evaluation run `{run_id}` is {run.lifecycle_status} with verdict "
                f"{run.verdict or 'none'}; promotion requires a COMPLETED run with "
                "verdict PASS."
            ),
        )


def _record_lifecycle_transition(
    *,
    entry: ModelCatalogueEntry,
    to_state: ModelLifecycleState,
    reason: str,
    requested_by: str,
    approved_by: str | None,
    approval_evidence_ref: str | None,
) -> ModelLifecycleTransitionResponse:
    """Durably apply one already-validated lifecycle state change."""

    now = _utc_now_iso()
    updates: dict[str, object] = {"lifecycle_state": to_state, "last_updated_at": now}
    if approval_evidence_ref:
        updates["approval_evidence_refs"] = [
            *entry.approval_evidence_refs,
            approval_evidence_ref,
        ]
    updated = entry.model_copy(update=updates)
    transition = ModelLifecycleTransitionRecord(
        event_id=f"mlc_{uuid4().hex[:16]}",
        entry_id=entry.entry_id,
        from_state=entry.lifecycle_state,
        to_state=to_state,
        reason=reason,
        requested_by=requested_by,
        approved_by=approved_by,
        approval_evidence_ref=approval_evidence_ref,
        recorded_at=now,
    )
    upsert_model_catalogue_entry(updated)
    get_model_catalogue_repository().append_lifecycle_event(transition)
    return ModelLifecycleTransitionResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.model_catalogue_store_mode,
        entry=updated,
        transition=transition,
    )


def apply_model_lifecycle_transition(
    entry_id: str,
    request: ModelLifecycleTransitionRequest,
    caller: AuthenticatedCaller,
) -> ModelLifecycleTransitionResponse:
    """Apply one single-principal lifecycle transition to a catalogue entry.

    Safety and administrative targets only: taking a model out of service, or
    moving it through cataloguing and evaluation, is applied immediately by
    one verified principal and honestly records that no approval existed.
    Serving promotions are risk-increasing and refused here with guidance to
    the governed two-step flow (issue #245).
    """

    _require_provider_control_authorization(caller)
    _require_durable_catalogue_store()
    entry = _get_required_catalogue_entry(entry_id)
    if request.to_state in MODEL_SERVING_PROMOTION_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transition to {request.to_state.value} expands serving posture and must go "
                "through the governed two-step promotion flow (issue #245): state the intent "
                "via promotion-requests, then a distinct verified credential approves via "
                "promotion-approvals."
            ),
        )
    _validate_lifecycle_edge(entry, request.to_state)
    return _record_lifecycle_transition(
        entry=entry,
        to_state=request.to_state,
        reason=request.reason,
        requested_by=verified_caller_identity(caller),
        approved_by=None,
        approval_evidence_ref=None,
    )


def _promotion_action_payload(
    *,
    entry: ModelCatalogueEntry,
    to_state: ModelLifecycleState,
    evaluation_run_id: str,
    reason: str,
) -> dict[str, str | None]:
    """The exact action the approver signs off on.

    Pins the entry's current lifecycle state and exact revision identity: a
    promotion reviewed against one baseline must not execute against another,
    so a state or revision change between request and approval refuses the
    stale approval instead of executing it (issue #245).
    """

    return {
        "action_type": GovernedActionType.MODEL_LIFECYCLE_PROMOTE.value,
        "entry_id": entry.entry_id,
        "from_state": entry.lifecycle_state.value,
        "to_state": to_state.value,
        "provider_id": entry.provider_id,
        "model_family": entry.model_family,
        "model_revision": entry.model_revision,
        "deployment": entry.deployment,
        "evaluation_run_id": evaluation_run_id,
        "reason": reason,
    }


def request_model_promotion(
    entry_id: str,
    request: ModelPromotionIntentRequest,
    caller: AuthenticatedCaller,
) -> GovernedActionResponse:
    """Step one of governed serving promotion: record the intent under the requester's credential.

    The promotion is fully validated first - serving target, lifecycle edge,
    and PASS-verdict eval evidence - so a pending action is never parked on a
    promotion that is not currently executable.
    """

    _require_provider_control_authorization(caller)
    _require_durable_catalogue_store()
    entry = _get_required_catalogue_entry(entry_id)
    if request.to_state not in MODEL_SERVING_PROMOTION_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{request.to_state.value} is not a serving-promotion target; apply it as a "
                "single-principal transition via lifecycle-transitions."
            ),
        )
    _validate_lifecycle_edge(entry, request.to_state)
    _require_pass_verdict_evaluation_run(request.evaluation_run_id)
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.MODEL_LIFECYCLE_PROMOTE,
        target=entry_id,
        payload=_promotion_action_payload(
            entry=entry,
            to_state=request.to_state,
            evaluation_run_id=request.evaluation_run_id,
            reason=request.reason,
        ),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Promotion of `{entry_id}` from {entry.lifecycle_state.value} to "
            f"{request.to_state.value} is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            f"Eval evidence: run `{request.evaluation_run_id}` (COMPLETED, verdict PASS).",
        ],
    )


def approve_model_promotion(
    entry_id: str,
    request: ModelPromotionApprovalRequest,
    caller: AuthenticatedCaller,
) -> ModelPromotionApprovalResponse:
    """Step two: a distinct verified credential approves the exact action, which executes it."""

    _require_provider_control_authorization(caller)
    _require_durable_catalogue_store()
    entry = _get_required_catalogue_entry(entry_id)
    outcome: dict[str, object] = {}

    def _execute_promotion(record: GovernedActionRecord) -> None:
        to_state = ModelLifecycleState(str(record.action_payload.get("to_state")))
        evaluation_run_id = str(record.action_payload.get("evaluation_run_id"))
        _validate_lifecycle_edge(entry, to_state)
        _require_pass_verdict_evaluation_run(evaluation_run_id)
        outcome["response"] = _record_lifecycle_transition(
            entry=entry,
            to_state=to_state,
            reason=str(record.action_payload.get("reason")),
            requested_by=(f"{record.requester_caller_app} (credential {record.requester_key_id})"),
            approved_by=verified_caller_identity(caller),
            approval_evidence_ref=f"evaluation-run:{evaluation_run_id}",
        )

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=entry_id,
        expected_hash=request.action_hash,
        current_payload_builder=lambda record: _promotion_action_payload(
            entry=entry,
            to_state=ModelLifecycleState(str(record.action_payload.get("to_state"))),
            evaluation_run_id=str(record.action_payload.get("evaluation_run_id")),
            reason=str(record.action_payload.get("reason")),
        ),
        attribution=request.approved_by,
        execute=_execute_promotion,
    )
    transition_response = cast(ModelLifecycleTransitionResponse, outcome["response"])
    return ModelPromotionApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.model_catalogue_store_mode,
        entry=transition_response.entry,
        transition=transition_response.transition,
        governed_action=executed,
        summary=[
            f"Promoted `{entry_id}` to {transition_response.entry.lifecycle_state.value} "
            f"under governed action `{executed.action_id}`.",
            f"Requested under credential `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}`.",
            f"Evidence: `{transition_response.transition.approval_evidence_ref}`.",
        ],
    )


def degrade_model_capability(
    entry_id: str,
    request: ModelCapabilityDegradationRequest,
    caller: AuthenticatedCaller,
) -> ModelCapabilityDegradationResponse:
    """Degrade one capability dimension on a catalogue entry, immediately.

    Safety direction (issue #245, slice 2): containing an observed regression
    takes one verified principal and no approval step. The underlying
    assessed fact is never rewritten - the degradation overrides it for
    requirement routing only while present.
    """

    _require_provider_control_authorization(caller)
    _require_durable_catalogue_store()
    entry = _get_required_catalogue_entry(entry_id)
    if request.dimension not in DEGRADABLE_CAPABILITY_DIMENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"`{request.dimension}` is not a degradable capability dimension; requirement "
                f"routing enforces: {sorted(DEGRADABLE_CAPABILITY_DIMENSIONS)}."
            ),
        )
    existing = entry.capability_degradations.get(request.dimension)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Capability `{request.dimension}` on `{entry_id}` is already degraded "
                f"(by {existing.degraded_by} at {existing.degraded_at}); the active "
                "degradation's provenance is not overwritable."
            ),
        )
    degradation = ModelCapabilityDegradation(
        dimension=request.dimension,
        reason=request.reason,
        degraded_by=verified_caller_identity(caller),
        degraded_at=_utc_now_iso(),
    )
    updated = entry.model_copy(
        update={
            "capability_degradations": {
                **entry.capability_degradations,
                request.dimension: degradation,
            },
            "last_updated_at": degradation.degraded_at,
        }
    )
    upsert_model_catalogue_entry(updated)
    return ModelCapabilityDegradationResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.model_catalogue_store_mode,
        entry=updated,
        degradation=degradation,
    )


def _capability_restore_payload(
    *,
    entry: ModelCatalogueEntry,
    degradation: ModelCapabilityDegradation,
    evaluation_run_id: str,
    reason: str,
) -> dict[str, str | None]:
    """The exact action the approver signs off on.

    Pins the full degradation being cleared: if the overlay changes between
    request and approval (re-degraded with a new reason, or already cleared),
    the stale approval refuses instead of executing (issue #245, slice 2).
    """

    return {
        "action_type": GovernedActionType.MODEL_CAPABILITY_RESTORE.value,
        "entry_id": entry.entry_id,
        "dimension": degradation.dimension,
        "degradation_reason": degradation.reason,
        "degraded_by": degradation.degraded_by,
        "degraded_at": degradation.degraded_at,
        "evaluation_run_id": evaluation_run_id,
        "reason": reason,
    }


def _get_required_capability_degradation(
    entry: ModelCatalogueEntry, dimension: str
) -> ModelCapabilityDegradation:
    degradation = entry.capability_degradations.get(dimension)
    if degradation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Capability `{dimension}` on `{entry.entry_id}` is not degraded; "
                "there is nothing to restore."
            ),
        )
    return degradation


def request_model_capability_restore(
    entry_id: str,
    request: ModelCapabilityRestoreIntentRequest,
    caller: AuthenticatedCaller,
) -> GovernedActionResponse:
    """Step one of governed capability restore: record the intent under the requester's credential.

    Clearing a degradation re-exposes the underlying evidence-derived fact to
    requirement routing - risk-increasing, so the restore is validated first
    (active degradation, PASS-verdict eval evidence) and executes only under
    a distinct verified approval.
    """

    _require_provider_control_authorization(caller)
    _require_durable_catalogue_store()
    entry = _get_required_catalogue_entry(entry_id)
    degradation = _get_required_capability_degradation(entry, request.dimension)
    _require_pass_verdict_evaluation_run(request.evaluation_run_id)
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.MODEL_CAPABILITY_RESTORE,
        target=entry_id,
        payload=_capability_restore_payload(
            entry=entry,
            degradation=degradation,
            evaluation_run_id=request.evaluation_run_id,
            reason=request.reason,
        ),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Restore of capability `{request.dimension}` on `{entry_id}` is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            f"The capability stays degraded ({degradation.reason}) until then.",
        ],
    )


def approve_model_capability_restore(
    entry_id: str,
    request: ModelCapabilityRestoreApprovalRequest,
    caller: AuthenticatedCaller,
) -> ModelCapabilityRestoreApprovalResponse:
    """Step two: a distinct verified credential approves the exact action, which executes it."""

    _require_provider_control_authorization(caller)
    _require_durable_catalogue_store()
    entry = _get_required_catalogue_entry(entry_id)
    outcome: dict[str, object] = {}

    def _execute_restore(record: GovernedActionRecord) -> None:
        dimension = str(record.action_payload.get("dimension"))
        _require_pass_verdict_evaluation_run(str(record.action_payload.get("evaluation_run_id")))
        remaining = {
            key: value for key, value in entry.capability_degradations.items() if key != dimension
        }
        updated = entry.model_copy(
            update={"capability_degradations": remaining, "last_updated_at": _utc_now_iso()}
        )
        upsert_model_catalogue_entry(updated)
        outcome["entry"] = updated

    def _current_payload(record: GovernedActionRecord) -> dict[str, str | None]:
        dimension = str(record.action_payload.get("dimension"))
        return _capability_restore_payload(
            entry=entry,
            degradation=_get_required_capability_degradation(entry, dimension),
            evaluation_run_id=str(record.action_payload.get("evaluation_run_id")),
            reason=str(record.action_payload.get("reason")),
        )

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=entry_id,
        expected_hash=request.action_hash,
        current_payload_builder=_current_payload,
        attribution=request.approved_by,
        execute=_execute_restore,
    )
    updated_entry = cast(ModelCatalogueEntry, outcome["entry"])
    return ModelCapabilityRestoreApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.model_catalogue_store_mode,
        entry=updated_entry,
        governed_action=executed,
        summary=[
            f"Restored capability `{executed.action_payload.get('dimension')}` on `{entry_id}` "
            f"under governed action `{executed.action_id}`.",
            f"Requested under credential `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}`.",
            "The cleared degradation is pinned inside this action's payload.",
        ],
    )


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
