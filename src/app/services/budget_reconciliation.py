"""Governed reconciliation of unresolved billable exposure (issue #329).

An attempt that carried billable risk but never revealed trustworthy usage
holds its reserved maximum in the hard-budget counter (basis
``UNRESOLVED_MAX``): nothing established that the provider billed less, so
the estimate is reporting posture, never settlement evidence. The ONLY way
that headroom returns is this two-step governed action: an operator states
the provider-evidenced charge (invoice line, billing-console export) under
one verified credential, and a distinct verified credential approves the
exact hash. Releasing admission capacity is risk-increasing; holding it is
the automatic safe direction and needs no approval.

The freshness hash pins the exposure's basis at request time: if usage
evidence or another reconciliation resolves the row between request and
approval, the rebuilt payload no longer matches and the approval refuses
instead of double-releasing.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionStatus,
    GovernedActionType,
)
from app.contracts.providers import (
    BudgetReconciliationApprovalRequest,
    BudgetReconciliationApprovalResponse,
    BudgetReconciliationIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.provider_budget_policy import reconcile_attempt_spend
from app.services.provider_operations_store import get_provider_operations_store

_RECONCILABLE_BASES = ("UNRESOLVED_MAX", "RESERVED_MAX")


def _require_provider_control_authorization(caller: AuthenticatedCaller) -> None:
    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )


def _amount_str(value: float) -> str:
    return f"{value:.8f}"


def _reconciliation_payload(
    *,
    debit_id: str,
    evidenced_amount_usd: float,
    evidence_ref: str,
    input_tokens: int | None,
    output_tokens: int | None,
    exposure_basis: str,
    held_amount_usd: float,
) -> dict[str, str | None]:
    """The exact action the approver signs off on: the debit, the evidenced
    charge, where to verify it, and the exposure's basis AND held amount at
    request time - a row resolved or changed by other means between request
    and approval rebuilds to a different hash and refuses. The pinned held
    amount is also what makes a crash-recovery replay report the true
    released difference after the row itself has been overwritten."""

    return {
        "action_type": GovernedActionType.BUDGET_RECONCILIATION.value,
        "debit_id": debit_id,
        "evidenced_amount_usd": _amount_str(evidenced_amount_usd),
        "evidence_ref": evidence_ref,
        "input_tokens": str(input_tokens) if input_tokens is not None else None,
        "output_tokens": str(output_tokens) if output_tokens is not None else None,
        "exposure_basis": exposure_basis,
        "held_amount_usd": _amount_str(held_amount_usd),
    }


def request_budget_reconciliation(
    request: BudgetReconciliationIntentRequest, caller: AuthenticatedCaller
) -> GovernedActionResponse:
    """Step one: record the reconciliation intent under the requester's credential."""

    _require_provider_control_authorization(caller)
    row = get_provider_operations_store().get_attempt_debit(debit_id=request.debit_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No attempt debit exists for `{request.debit_id}`.",
        )
    if row.basis not in _RECONCILABLE_BASES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Attempt debit `{request.debit_id}` is {row.basis}, not unresolved "
                "exposure; only UNRESOLVED_MAX (or a crash-orphaned RESERVED_MAX) "
                "reconciles."
            ),
        )
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.BUDGET_RECONCILIATION,
        target=request.debit_id,
        payload=_reconciliation_payload(
            debit_id=request.debit_id,
            evidenced_amount_usd=request.evidenced_amount_usd,
            evidence_ref=request.evidence_ref,
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            exposure_basis=row.basis,
            held_amount_usd=row.amount_usd,
        ),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Reconciliation of debit `{request.debit_id}` ({row.basis}, "
            f"{_amount_str(row.amount_usd)} USD held) to the evidenced charge "
            f"{_amount_str(request.evidenced_amount_usd)} USD is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            "The held maximum stays in the budget counter until the approval executes.",
        ],
    )


def approve_budget_reconciliation(
    request: BudgetReconciliationApprovalRequest, caller: AuthenticatedCaller
) -> BudgetReconciliationApprovalResponse:
    """Step two: a distinct verified credential approves; execution settles
    the exposure to the evidenced charge and releases the difference."""

    _require_provider_control_authorization(caller)
    store = get_provider_operations_store()

    # A lost response is recoverable without a second release: an EXECUTED
    # action with the same hash returns the SAME evidenced outcome.
    existing = store.get_governed_action(request.action_id)
    if (
        existing is not None
        and existing.status is GovernedActionStatus.EXECUTED
        and existing.action_hash == request.action_hash
        and existing.result_payload is not None
    ):
        return _reconciliation_response_from_result(existing)

    def _rebuild_payload(record: GovernedActionRecord) -> dict[str, str | None]:
        debit_id = str(record.action_payload.get("debit_id"))
        row = store.get_attempt_debit(debit_id=debit_id)
        raw_input = record.action_payload.get("input_tokens")
        raw_output = record.action_payload.get("output_tokens")
        return _reconciliation_payload(
            debit_id=debit_id,
            evidenced_amount_usd=float(  # monetary-float-ok: parses the hash-pinned decimal string back into the envelope's float form
                str(record.action_payload.get("evidenced_amount_usd"))
            ),
            evidence_ref=str(record.action_payload.get("evidence_ref")),
            input_tokens=int(raw_input) if raw_input is not None else None,
            output_tokens=int(raw_output) if raw_output is not None else None,
            # A deleted or already-resolved row rebuilds to a different
            # basis (and a changed amount to a different held figure), so the
            # pending approval stops matching - the 409 says the action
            # changed, which is the truth.
            exposure_basis=row.basis if row is not None else "ABSENT",
            held_amount_usd=row.amount_usd if row is not None else 0.0,
        )

    outcome: dict[str, str] = {}

    def _execute_reconciliation(record: GovernedActionRecord) -> None:
        debit_id = str(record.action_payload.get("debit_id"))
        evidenced = float(  # monetary-float-ok: parses the hash-pinned decimal string back into the envelope's float form
            str(record.action_payload.get("evidenced_amount_usd"))
        )
        raw_input = record.action_payload.get("input_tokens")
        raw_output = record.action_payload.get("output_tokens")
        # The held maximum comes from the HASH-PINNED payload, not the live
        # row: after a crash between the counter release and the EXECUTED
        # write, the row already carries the evidenced amount, and only the
        # pinned figure lets the recovery replay report the true release.
        held_amount = float(  # monetary-float-ok: parses the hash-pinned decimal string
            str(record.action_payload.get("held_amount_usd"))
        )
        settled = reconcile_attempt_spend(
            debit_id=debit_id,
            evidenced_amount_usd=evidenced,
            input_tokens=int(raw_input) if raw_input is not None else None,
            output_tokens=int(raw_output) if raw_output is not None else None,
            rate_card_ref=None,
        )
        if not settled:
            # Idempotent under the action identity: a crash between the
            # counter release and the EXECUTED write converges here on the
            # claiming credential's resume.
            current = store.get_attempt_debit(debit_id=debit_id)
            if not (
                current is not None
                and current.basis == "RECONCILED"
                and round(current.amount_usd, 8) == round(evidenced, 8)
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Attempt debit `{debit_id}` was resolved by other means while "
                        "this approval executed; no release was applied."
                    ),
                )
        outcome["debit_id"] = debit_id
        outcome["evidenced_amount_usd"] = _amount_str(evidenced)
        outcome["released_amount_usd"] = _amount_str(round(held_amount - evidenced, 8))

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=_expected_target(request),
        expected_hash=request.action_hash,
        current_payload_builder=_rebuild_payload,
        attribution=request.approved_by,
        execute=_execute_reconciliation,
        result_payload_builder=lambda: dict(outcome),
        resume_interrupted_claim=request.resume_interrupted_claim,
    )
    evidenced_usd = float(
        outcome["evidenced_amount_usd"]
    )  # monetary-float-ok: restates the executed outcome
    released_usd = float(
        outcome["released_amount_usd"]
    )  # monetary-float-ok: restates the executed outcome
    return _build_response(
        executed,
        debit_id=outcome["debit_id"],
        evidenced_amount_usd=evidenced_usd,
        released_amount_usd=released_usd,
    )


def _expected_target(request: BudgetReconciliationApprovalRequest) -> str:
    record = get_provider_operations_store().get_governed_action(request.action_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed action exists for `{request.action_id}`.",
        )
    return record.target


def _reconciliation_response_from_result(
    record: GovernedActionRecord,
) -> BudgetReconciliationApprovalResponse:
    payload = record.result_payload or {}
    evidenced_usd = float(
        str(payload.get("evidenced_amount_usd"))
    )  # monetary-float-ok: replays the durable result
    released_usd = float(
        str(payload.get("released_amount_usd"))
    )  # monetary-float-ok: replays the durable result
    return _build_response(
        record,
        debit_id=str(payload.get("debit_id")),
        evidenced_amount_usd=evidenced_usd,
        released_amount_usd=released_usd,
    )


def _build_response(
    record: GovernedActionRecord,
    *,
    debit_id: str,
    evidenced_amount_usd: float,
    released_amount_usd: float,
) -> BudgetReconciliationApprovalResponse:
    return BudgetReconciliationApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        debit_id=debit_id,
        evidenced_amount_usd=evidenced_amount_usd,
        released_amount_usd=released_amount_usd,
        summary=[
            f"Debit `{debit_id}` reconciled to the evidenced charge "
            f"{_amount_str(evidenced_amount_usd)} USD under governed action "
            f"`{record.action_id}`.",
            f"Hard-budget headroom released: {_amount_str(released_amount_usd)} USD.",
            f"Requested under credential `{record.requester_key_id}` and approved under "
            f"distinct credential `{record.approver_key_id}`.",
        ],
    )
