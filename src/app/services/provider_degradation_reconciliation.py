"""Legacy circuit-breaker state reconciliation (issue #234).

Issue #176 S3 moved degradation bookkeeping from the bare
``live_text_generation`` key to ``live_text_generation:<provider_id>`` so the
primary's failures could never open the alternate's breaker. That migration
treated rows still under the bare key as stale transient bookkeeping, which is
true of a closed breaker and wrong for an open one.

An OPEN breaker is not bookkeeping. It is an active protection decision: the
runtime is refusing live calls because it has already judged a provider to be
failing. If that row becomes unreadable at the new key, the next deployment
silently resumes traffic to a provider the system had ruled unsafe, with no
operator action and no evidence that anything was overridden.

So reconciliation runs at startup and is deliberately conservative: it carries
an open circuit across to the provider-scoped key with its cooldown intact,
drops closed rows without ceremony, and refuses to delete an open row it cannot
attribute - that becomes a startup finding naming the orphaned state instead.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from app.repositories.provider_operations_repository import ProviderDegradationStateRecord
from app.services.provider_degradation_state import (
    DEGRADATION_KEY_PREFIX,
    degradation_key_for,
)
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.provider_operations_store import get_provider_operations_store
from app.services.runtime_readiness import get_provider_operations_store_runtime_status

LEGACY_DEGRADATION_KEY = DEGRADATION_KEY_PREFIX


def reconcile_legacy_degradation_state() -> list[str]:
    """Migrate pre-#176-S3 breaker state, returning startup findings.

    Idempotent: the legacy row is removed once its meaning has been carried
    over, so a second run finds nothing to do. A provider-scoped row that
    already exists wins - it is current bookkeeping, and the legacy row can
    only be older.
    """

    store_status = get_provider_operations_store_runtime_status()
    if store_status.status != "READY":
        # Resolving the store would raise here and take startup down with an
        # error that bypasses the warn/enforce policy entirely. Report it as a
        # finding instead, and say plainly what was not done.
        return [
            "provider degradation: legacy circuit-breaker reconciliation was skipped because "
            f"the provider-operations store is not ready ({store_status.detail}). If a "
            "pre-migration OPEN circuit exists it has not been carried over, so a provider "
            "the runtime had already refused may be called again."
        ]

    repository = get_provider_operations_store()
    legacy = repository.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY)
    if legacy is None:
        return []

    if not circuit_is_open(legacy):
        # A closed breaker carries no protection decision worth preserving.
        repository.reset_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY)
        return []

    provider_id = resolve_provider_execution_config().provider_id
    if not provider_id:
        # Deleting here would discard an open circuit that no longer has an
        # owner - exactly the silent re-enable this reconciliation exists to
        # prevent. Leave the row and make an operator look at it.
        return [
            "provider degradation: an OPEN circuit is recorded under the pre-migration key "
            f"'{LEGACY_DEGRADATION_KEY}' (open until {legacy.circuit_open_until}, "
            f"{legacy.consecutive_failure_count} consecutive failures) but no live text "
            "provider identity is configured, so it cannot be attributed to a provider. "
            "The row has been left in place: configure the provider identity it belongs to, "
            "or clear it explicitly through provider operations."
        ]

    scoped_key = degradation_key_for(provider_id)
    if repository.get_degradation_state(degradation_key=scoped_key) is None:
        repository.save_degradation_state(replace(legacy, degradation_key=scoped_key))
    repository.reset_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY)
    return []


def circuit_is_open(record: ProviderDegradationStateRecord) -> bool:
    """Whether ``record`` carries a cooldown that has not yet elapsed.

    Deliberately not reusing the degradation module's remaining-seconds
    helper: that one clears an expired cooldown as a side effect, and a
    migration decision must not mutate the state it is deciding about.
    """

    if record.circuit_open_until is None:
        return False
    return datetime.fromisoformat(record.circuit_open_until) > datetime.now(UTC)
