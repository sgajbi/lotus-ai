"""Governed lifecycle and capability control on the model catalogue (issue #245).

Split from services/model_catalogue.py when the module budget fired: the
catalogue module owns identity truth, seeding and eligibility reads; this
module owns the governed state changes on it - lifecycle transitions, serving
promotions, capability degradation and its governed restore - every one
composing the #157 governed-action primitive and the risk-direction rule.
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
    ModelCapabilityDegradation,
    ModelCapabilityDegradationRequest,
    ModelCapabilityDegradationResponse,
    ModelCapabilityRestoreApprovalRequest,
    ModelCapabilityRestoreApprovalResponse,
    ModelCapabilityRestoreIntentRequest,
    ModelCatalogueEntry,
    ModelLifecycleState,
    ModelLifecycleTransitionRecord,
    ModelLifecycleTransitionRequest,
    ModelLifecycleTransitionResponse,
    ModelPromotionApprovalRequest,
    ModelPromotionApprovalResponse,
    ModelPromotionIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.kill_switch_control import verified_caller_identity
from app.services.model_catalogue import upsert_model_catalogue_entry
from app.services.model_catalogue_store import get_model_catalogue_repository


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
