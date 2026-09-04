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

from app.contracts.model_catalogue import derive_model_catalogue_entry_id
from app.repositories.provider_operations_repository import ProviderDegradationStateRecord
from app.services.provider_degradation_state import (
    DEGRADATION_KEY_PREFIX,
    degradation_key_for,
)
from app.services.provider_connection_material import configured_connection_materials
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


def reconcile_provider_keyed_degradation_state() -> list[str]:
    """Migrate pre-#304 provider-keyed breaker rows to candidate keys.

    Issue #304 re-keyed the breaker from ``live_text_generation:<provider>``
    to the candidate entry id. The same conservative rule as the bare-key
    migration applies, with one widening: an OPEN provider row was refusing
    every candidate of that provider, so it is carried to EVERY currently
    configured candidate of that provider - preserving the refusal is the
    safe direction; each candidate's breaker then closes on its own
    cooldown. Closed rows drop; provider-only keys still in live use (a
    config with no model identity) are untouched because such providers
    carry no connection material.
    """

    store_status = get_provider_operations_store_runtime_status()
    if store_status.status != "READY":
        return [
            "provider degradation: provider-keyed breaker reconciliation was skipped because "
            f"the provider-operations store is not ready ({store_status.detail})."
        ]
    config = resolve_provider_execution_config()
    try:
        materials = configured_connection_materials(config)
    except ValueError:
        # Malformed declared material is already its own startup finding.
        return []
    by_provider: dict[str, list[str]] = {}
    for material in materials.values():
        # The carried-over key must match the key shape the BREAKER derives
        # at runtime - the v1-shaped candidate identity - not the material
        # map's canonical id (issue #314 S2a keys materials canonically; the
        # breaker re-keys in S2b, and this derivation flips with it).
        candidate_key = derive_model_catalogue_entry_id(
            provider_id=material.provider_id,
            model_revision=material.model_version or material.model_id,
            deployment=material.deployment,
        )
        by_provider.setdefault(material.provider_id, []).append(candidate_key)
    repository = get_provider_operations_store()
    for provider_id, entry_ids in sorted(by_provider.items()):
        provider_key = f"{DEGRADATION_KEY_PREFIX}:{provider_id}"
        row = repository.get_degradation_state(degradation_key=provider_key)
        if row is None:
            continue
        if not circuit_is_open(row):
            repository.reset_degradation_state(degradation_key=provider_key)
            continue
        for entry_id in sorted(entry_ids):
            candidate_key = f"{DEGRADATION_KEY_PREFIX}:{entry_id}"
            if repository.get_degradation_state(degradation_key=candidate_key) is None:
                repository.save_degradation_state(replace(row, degradation_key=candidate_key))
        repository.reset_degradation_state(degradation_key=provider_key)
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
