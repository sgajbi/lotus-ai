"""An OPEN circuit survives the per-provider key migration (issue #234).

#176 S3 rekeyed degradation bookkeeping per provider identity and treated
rows left under the bare key as stale transient state. For a CLOSED breaker
that is true. For an OPEN one it is a safety defect: the row is an active
refusal to call a provider, and losing it re-enables that provider on the
next deployment with no operator action and no evidence.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.repositories.provider_operations_repository import ProviderDegradationStateRecord
from app.services.provider_degradation_reconciliation import (
    LEGACY_DEGRADATION_KEY,
    reconcile_legacy_degradation_state,
)
from app.services.provider_degradation_state import (
    build_provider_degradation_status,
    degradation_key_for,
    enforce_provider_degradation_preflight,
)
from app.services.provider_operations_store import (
    get_provider_operations_store,
    reset_provider_operations_store_cache,
)
from app.services.startup_policy import apply_startup_readiness_policy
from tests.support.migration_runner import upgrade_database_to_head

PRIMARY = "text.openai"


def _legacy_record(*, open_for_seconds: int | None, failures: int = 5) -> None:
    circuit_open_until = (
        (datetime.now(UTC) + timedelta(seconds=open_for_seconds)).isoformat()
        if open_for_seconds is not None
        else None
    )
    get_provider_operations_store().save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key=LEGACY_DEGRADATION_KEY,
            consecutive_failure_count=failures,
            last_failure_category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            circuit_open_until=circuit_open_until,
            timeout_failure_count=failures,
            rate_limited_failure_count=0,
            upstream_error_failure_count=0,
            updated_at=datetime.now(UTC).isoformat(),
        )
    )


def _enforcing_primary() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = PRIMARY
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 3
    settings.live_text_circuit_open_failure_count_threshold = 5
    settings.live_text_circuit_open_seconds = 60
    settings.startup_readiness_policy = "warn"


def test_an_open_legacy_circuit_still_refuses_execution_after_reconciliation() -> None:
    """The issue's evaluation condition: an open bare-key breaker present at
    startup leaves the candidate's breaker open, with the cooldown
    preserved, and live execution still refused. The migration is now a
    two-layer chain (issues #234, #304): bare key -> provider key ->
    candidate key, all within one startup."""

    _enforcing_primary()
    _legacy_record(open_for_seconds=900)

    apply_startup_readiness_policy()

    store = get_provider_operations_store()
    assert store.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY) is None
    # The intermediate provider-keyed row was itself carried forward.
    assert store.get_degradation_state(degradation_key=f"live_text_generation:{PRIMARY}") is None
    migrated = store.get_degradation_state(
        degradation_key=f"live_text_generation:{PRIMARY}:gpt-5.4"
    )
    assert migrated is not None
    assert migrated.consecutive_failure_count == 5
    assert migrated.last_failure_category is ProviderFailureCategory.PROVIDER_TIMEOUT

    status = build_provider_degradation_status(f"{PRIMARY}:gpt-5.4")
    assert status.status == "CIRCUIT_OPEN"
    assert status.circuit_open_remaining_seconds is not None
    assert status.circuit_open_remaining_seconds > 0

    with pytest.raises(ProviderExecutionError) as exc_info:
        enforce_provider_degradation_preflight()
    assert exc_info.value.category is ProviderFailureCategory.CIRCUIT_OPEN


def test_an_unattributable_open_circuit_is_a_finding_not_a_deletion() -> None:
    _enforcing_primary()
    settings.live_text_provider_id = None
    _legacy_record(open_for_seconds=900)

    evaluation = apply_startup_readiness_policy()

    assert any(LEGACY_DEGRADATION_KEY in finding for finding in evaluation.findings)
    assert any("cannot be attributed" in finding for finding in evaluation.findings)
    # Left in place: discarding it is the silent re-enable this prevents.
    assert (
        get_provider_operations_store().get_degradation_state(
            degradation_key=LEGACY_DEGRADATION_KEY
        )
        is not None
    )


def test_reconciliation_is_idempotent() -> None:
    _enforcing_primary()
    _legacy_record(open_for_seconds=900)

    assert reconcile_legacy_degradation_state() == []
    store = get_provider_operations_store()
    after_first = store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY))

    assert reconcile_legacy_degradation_state() == []
    assert store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY)) == after_first
    assert store.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY) is None


def test_a_current_provider_scoped_row_wins_over_the_legacy_row() -> None:
    _enforcing_primary()
    store = get_provider_operations_store()
    current = ProviderDegradationStateRecord(
        degradation_key=degradation_key_for(PRIMARY),
        consecutive_failure_count=1,
        last_failure_category=ProviderFailureCategory.PROVIDER_RATE_LIMITED,
        circuit_open_until=None,
        timeout_failure_count=0,
        rate_limited_failure_count=1,
        upstream_error_failure_count=0,
        updated_at=datetime.now(UTC).isoformat(),
    )
    store.save_degradation_state(current)
    _legacy_record(open_for_seconds=900)

    assert reconcile_legacy_degradation_state() == []

    assert store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY)) == current
    assert store.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY) is None


def test_a_closed_legacy_row_is_dropped_without_ceremony() -> None:
    _enforcing_primary()
    _legacy_record(open_for_seconds=None, failures=2)

    assert reconcile_legacy_degradation_state() == []

    store = get_provider_operations_store()
    assert store.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY) is None
    assert store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY)) is None


def test_an_expired_legacy_cooldown_is_closed_and_dropped() -> None:
    """Expiry is not openness: a cooldown that has elapsed carries no live
    protection decision, so it is bookkeeping like any other closed row."""

    _enforcing_primary()
    _legacy_record(open_for_seconds=-30)

    assert reconcile_legacy_degradation_state() == []

    store = get_provider_operations_store()
    assert store.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY) is None
    assert store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY)) is None


def test_the_migration_behaves_identically_on_the_sql_store(tmp_path: Path) -> None:
    """Production runs the SQL adapter in the promoted profile, so the case
    that matters must be proven there and not only in memory - a delete or an
    upsert that diverges between adapters would lose the open circuit exactly
    where losing it costs something."""

    _enforcing_primary()
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-breaker-migration.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_provider_operations_store_cache()

    _legacy_record(open_for_seconds=900)

    assert reconcile_legacy_degradation_state() == []

    store = get_provider_operations_store()
    assert store.get_degradation_state(degradation_key=LEGACY_DEGRADATION_KEY) is None
    migrated = store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY))
    assert migrated is not None
    assert migrated.consecutive_failure_count == 5
    assert build_provider_degradation_status(PRIMARY).status == "CIRCUIT_OPEN"

    # Idempotent against a durable store too.
    assert reconcile_legacy_degradation_state() == []
    assert store.get_degradation_state(degradation_key=degradation_key_for(PRIMARY)) == migrated


def test_an_open_provider_keyed_circuit_carries_to_every_candidate_of_that_provider() -> None:
    """Issue #304: an OPEN provider-keyed row was refusing every candidate of
    that provider, so the migration carries it to EACH configured candidate
    of the provider - preserving the refusal is the safe direction - and a
    CLOSED provider row drops without ceremony."""

    import json

    _enforcing_primary()
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": PRIMARY,
                "model_id": "gpt-5.4-mini",
                "api_base": "https://sibling.example/v1",
            }
        ]
    )
    store = get_provider_operations_store()
    open_until = (datetime.now(UTC) + timedelta(seconds=900)).isoformat()
    store.save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key=f"live_text_generation:{PRIMARY}",
            consecutive_failure_count=7,
            last_failure_category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            circuit_open_until=open_until,
            timeout_failure_count=7,
            rate_limited_failure_count=0,
            upstream_error_failure_count=0,
            updated_at=datetime.now(UTC).isoformat(),
        )
    )

    apply_startup_readiness_policy()

    assert store.get_degradation_state(degradation_key=f"live_text_generation:{PRIMARY}") is None
    for candidate_key in (
        f"live_text_generation:{PRIMARY}:gpt-5.4",
        f"live_text_generation:{PRIMARY}:gpt-5.4-mini",
    ):
        carried = store.get_degradation_state(degradation_key=candidate_key)
        assert carried is not None, candidate_key
        assert carried.circuit_open_until == open_until
        assert carried.consecutive_failure_count == 7

    # A CLOSED provider-keyed row is dropped, and nothing is created for it.
    store.save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key="live_text_generation:text.claude",
            consecutive_failure_count=1,
            last_failure_category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            circuit_open_until=None,
            timeout_failure_count=1,
            rate_limited_failure_count=0,
            upstream_error_failure_count=0,
            updated_at=datetime.now(UTC).isoformat(),
        )
    )
    settings.live_text_fallback_provider_id = "text.claude"
    settings.live_text_fallback_model_id = "claude-sonnet-5"
    settings.live_text_fallback_api_base = "https://alternate.example/v1"
    apply_startup_readiness_policy()
    assert store.get_degradation_state(degradation_key="live_text_generation:text.claude") is None
    assert (
        store.get_degradation_state(
            degradation_key="live_text_generation:text.claude:claude-sonnet-5"
        )
        is None
    )


def test_provider_keyed_reconciliation_edge_branches() -> None:
    """The skipped-store finding and the malformed-material bail-out: neither
    path writes anything, and each says exactly what it did not do."""

    from unittest.mock import patch

    from app.services.provider_degradation_reconciliation import (
        reconcile_provider_keyed_degradation_state,
    )

    _enforcing_primary()

    class _NotReady:
        status = "BLOCKED"
        detail = "store offline"

    with patch(
        "app.services.provider_degradation_reconciliation."
        "get_provider_operations_store_runtime_status",
        return_value=_NotReady(),
    ):
        findings = reconcile_provider_keyed_degradation_state()
    assert any("was skipped" in finding for finding in findings)

    # Malformed declared material is its own startup finding; reconciliation
    # neither duplicates it nor crashes.
    settings.provider_connections_json = "{not json"
    assert reconcile_provider_keyed_degradation_state() == []
