from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.services.provider_usage_accounting import AttemptDebit, resolve_effective_live_text_card
from app.contracts.providers import (
    ProviderBudgetPolicyResponse,
    ProviderBudgetState,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.repositories.provider_operations_repository import ProviderAttemptDebitRecord
from app.services.provider_operations_store import get_provider_operations_store
from app.services.provider_execution_config import resolve_provider_execution_config

_BUDGET_KEY = "live_text_generation"


@dataclass(frozen=True)
class ParsedProviderBudgetPolicy:
    budget_enforced: bool
    configuration_valid: bool
    budget_state: ProviderBudgetState
    current_spend_usd: float
    soft_budget_usd: float | None
    hard_budget_usd: float | None
    remaining_budget_usd: float | None
    findings: list[str]
    usage_to_budget_notes: list[str]


def build_provider_budget_policy() -> ProviderBudgetPolicyResponse:
    parsed = parse_provider_budget_policy()
    return ProviderBudgetPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=resolve_provider_execution_config().provider_mode,
        budget_enforced=parsed.budget_enforced,
        configuration_valid=parsed.configuration_valid,
        budget_state=parsed.budget_state,
        current_spend_usd=parsed.current_spend_usd,
        soft_budget_usd=parsed.soft_budget_usd,
        hard_budget_usd=parsed.hard_budget_usd,
        remaining_budget_usd=parsed.remaining_budget_usd,
        findings=parsed.findings,
        usage_to_budget_notes=parsed.usage_to_budget_notes,
    )


def parse_provider_budget_policy() -> ParsedProviderBudgetPolicy:
    findings: list[str] = []
    configuration_valid = True
    current_spend_usd = _load_current_spend_usd()
    enforcement = resolve_provider_execution_config().enforcement
    soft_budget_usd = enforcement.soft_budget_usd
    hard_budget_usd = enforcement.hard_budget_usd

    if soft_budget_usd is not None and soft_budget_usd <= 0:
        configuration_valid = False
        findings.append("Soft provider budget must be a positive USD value when configured.")
    if hard_budget_usd is not None and hard_budget_usd <= 0:
        configuration_valid = False
        findings.append("Hard provider budget must be a positive USD value when configured.")
    if (
        soft_budget_usd is not None
        and hard_budget_usd is not None
        and soft_budget_usd > hard_budget_usd
    ):
        configuration_valid = False
        findings.append("Soft provider budget must not exceed the hard provider budget.")
    if enforcement.budget_enforced and hard_budget_usd is None:
        configuration_valid = False
        findings.append(
            "Live-provider budget enforcement requires a configured hard budget threshold."
        )
    if enforcement.budget_enforced and resolve_effective_live_text_card() is None:
        configuration_valid = False
        findings.append(
            "Live-provider budget enforcement requires an effective live-text rate card "
            "so spend can be estimated (issue #178)."
        )

    remaining_budget_usd = None
    if hard_budget_usd is not None:
        remaining_budget_usd = round(max(hard_budget_usd - current_spend_usd, 0.0), 8)

    budget_state = _resolve_budget_state(
        budget_enforced=enforcement.budget_enforced,
        configuration_valid=configuration_valid,
        current_spend_usd=current_spend_usd,
        soft_budget_usd=soft_budget_usd,
        hard_budget_usd=hard_budget_usd,
    )

    if not findings:
        findings.append("Provider budget posture is internally consistent for the current phase.")

    return ParsedProviderBudgetPolicy(
        budget_enforced=enforcement.budget_enforced,
        configuration_valid=configuration_valid,
        budget_state=budget_state,
        current_spend_usd=current_spend_usd,
        soft_budget_usd=soft_budget_usd,
        hard_budget_usd=hard_budget_usd,
        remaining_budget_usd=remaining_budget_usd,
        findings=findings,
        usage_to_budget_notes=[
            "Tracked spend is recorded durably per provider attempt at the attempt boundary (issue #289): actual usage debits as actual, billable-risk failures debit conservatively, and an execution whose every attempt fails still moves the envelope.",
            "Hard-limit admission is an atomic per-attempt check-and-reserve on the budget row (issue #300): each attempt reserves its governed maximum (input bounded by request-body bytes, output by the enforced cap) in one store transaction before the provider is called, then settles to the evidenced amount - concurrent replicas cannot jointly overshoot the limit, and a crash before settlement leaves the conservative reservation counted.",
            "Soft budget posture is advisory and inspectable; hard budget posture is blocking when enforcement is enabled.",
            "Tracked spend now flows through the configured provider-operations store so budget posture can remain durable when the SQL-backed provider-operations path is enabled.",
        ],
    )


def enforce_provider_budget() -> None:
    """Fast-path budget preflight: refuse an execution whose observed spend
    already reached the hard limit. This read is advisory under concurrency
    - the enforcement point that makes the limit actually hard is the
    atomic per-attempt check-and-reserve (issue #300), which this preflight
    merely short-circuits ahead of."""

    parsed = parse_provider_budget_policy()
    if not parsed.budget_enforced:
        return
    if not parsed.configuration_valid:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_BUDGET_CONFIGURATION,
            message="Live-provider budget configuration is invalid and cannot be enforced safely.",
        )
    if parsed.budget_state == ProviderBudgetState.HARD_LIMIT_BLOCKED:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.BUDGET_EXCEEDED,
            message="Live-provider hard budget threshold has been reached.",
        )


def record_attempt_spend(
    *,
    execution_id: str,
    candidate_entry_id: str,
    provider_id: str,
    model_revision: str | None,
    attempt_index: int,
    debit: AttemptDebit,
) -> bool:
    """Durably debit one provider attempt at its boundary (issue #289).

    The identity is derived from the execution/candidate/attempt context, so
    recording is idempotent: a crash after the attempt loses nothing, and a
    duplicate recording is a complete no-op. The budget counter advances in
    the same transaction, which is why an execution whose every attempt
    fails still moves the envelope - spend becomes real per attempt, not at
    response settlement.

    The candidate segment is the catalogue entry id, never the provider id
    (issue #299): two model candidates at the same provider are normal
    serving topology, and a provider-keyed identity would silently swallow
    the second candidate's attempt 0 as a duplicate of the first's. The
    row persists the full serving identity for later audit.
    """

    repository = get_provider_operations_store()
    return repository.record_attempt_debit(
        ProviderAttemptDebitRecord(
            debit_id=f"adbt:{execution_id}:{candidate_entry_id}:{attempt_index}",
            provider_id=provider_id,
            basis=debit.basis,
            amount_usd=debit.amount_usd,
            input_tokens=debit.input_tokens,
            output_tokens=debit.output_tokens,
            rate_card_ref=debit.rate_card_ref,
            recorded_at=_utcnow(),
            candidate_entry_id=candidate_entry_id,
            model_revision=model_revision,
            attempt_index=attempt_index,
        ),
        budget_key=_BUDGET_KEY,
    )


def reserve_attempt_spend(
    *,
    execution_id: str,
    candidate_entry_id: str,
    provider_id: str,
    model_revision: str | None,
    attempt_index: int,
    reservation: AttemptDebit,
) -> str:
    """Atomically reserve one attempt's governed maximum against the global
    budget row BEFORE the provider is called (issue #300).

    "Hard" means enforceable under concurrency: the limit check, the
    reservation row (basis ``RESERVED_MAX``) and the counter advance are one
    store transaction, so two replicas cannot both admit the last available
    budget. The reservation amount is the provably safe maximum - input
    bounded by the request body's byte count (a byte-level token is at
    least one byte) plus the provider-enforced output cap - not the
    documented ~4-bytes/token estimate the request ceiling uses. With
    budget enforcement off the reservation still records (settlement keeps
    evidence exact) but nothing refuses. Returns RESERVED, DUPLICATE (the
    same attempt already reserved or settled - crash-retry convergence), or
    REFUSED (nothing written).
    """

    enforcement = resolve_provider_execution_config().enforcement
    hard_limit = enforcement.hard_budget_usd if enforcement.budget_enforced else None
    repository = get_provider_operations_store()
    return repository.reserve_attempt_debit(
        ProviderAttemptDebitRecord(
            debit_id=f"adbt:{execution_id}:{candidate_entry_id}:{attempt_index}",
            provider_id=provider_id,
            basis="RESERVED_MAX",
            amount_usd=reservation.amount_usd,
            input_tokens=reservation.input_tokens,
            output_tokens=reservation.output_tokens,
            rate_card_ref=reservation.rate_card_ref,
            recorded_at=_utcnow(),
            candidate_entry_id=candidate_entry_id,
            model_revision=model_revision,
            attempt_index=attempt_index,
        ),
        budget_key=_BUDGET_KEY,
        hard_limit_usd=hard_limit,
    )


def settle_attempt_spend(
    *,
    execution_id: str,
    candidate_entry_id: str,
    attempt_index: int,
    debit: AttemptDebit | None,
) -> bool:
    """Settle a reservation to the attempt's evidenced debit in one
    transaction with the counter adjustment (issue #300) - or release it to
    zero (basis ``RELEASED``) when the attempt proved non-billable (429,
    pre-connect failure). Idempotent: only a still-reserved row settles. A
    crash before settlement leaves the conservative reservation standing -
    over-counting is the safe direction for a hard limit.
    """

    repository = get_provider_operations_store()
    debit_id = f"adbt:{execution_id}:{candidate_entry_id}:{attempt_index}"
    if debit is None:
        return repository.settle_attempt_debit(
            debit_id=debit_id,
            budget_key=_BUDGET_KEY,
            basis="RELEASED",
            amount_usd=0.0,
            input_tokens=None,
            output_tokens=None,
            rate_card_ref=None,
            settled_at=_utcnow(),
        )
    return repository.settle_attempt_debit(
        debit_id=debit_id,
        budget_key=_BUDGET_KEY,
        basis=debit.basis,
        amount_usd=debit.amount_usd,
        input_tokens=debit.input_tokens,
        output_tokens=debit.output_tokens,
        rate_card_ref=debit.rate_card_ref,
        settled_at=_utcnow(),
    )


def spent_for_execution(execution_id: str) -> float:
    """This execution's consumed spend, from its durable attempt debits
    (issue #290): the caller's cost ceiling admits or refuses the next
    attempt against exactly the number the envelope recorded."""

    repository = get_provider_operations_store()
    return repository.sum_attempt_debits(debit_id_prefix=f"adbt:{execution_id}:")


def reset_provider_budget_state() -> None:
    repository = get_provider_operations_store()
    repository.reset_budget_state(budget_key=_BUDGET_KEY)


def _resolve_budget_state(
    *,
    budget_enforced: bool,
    configuration_valid: bool,
    current_spend_usd: float,
    soft_budget_usd: float | None,
    hard_budget_usd: float | None,
) -> ProviderBudgetState:
    if not budget_enforced:
        return ProviderBudgetState.NOT_ENFORCED
    if not configuration_valid:
        return ProviderBudgetState.INVALID
    if hard_budget_usd is not None and current_spend_usd >= hard_budget_usd:
        return ProviderBudgetState.HARD_LIMIT_BLOCKED
    if soft_budget_usd is not None and current_spend_usd >= soft_budget_usd:
        return ProviderBudgetState.SOFT_LIMIT_REACHED
    return ProviderBudgetState.BELOW_SOFT_LIMIT


def _load_current_spend_usd() -> float:
    repository = get_provider_operations_store()
    record = repository.get_budget_state(budget_key=_BUDGET_KEY)
    if record is None:
        return 0.0
    return round(record.current_spend_usd, 8)


def _utcnow() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
