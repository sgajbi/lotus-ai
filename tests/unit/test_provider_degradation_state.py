from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.services.provider_degradation_state import (
    build_provider_degradation_status,
    enforce_provider_degradation_preflight,
    record_provider_failure,
    record_successful_provider_execution,
)
from app.services.provider_operations_store import (
    get_provider_operations_store,
    reset_provider_operations_store_cache,
)
from app.providers.base import ProviderExecutionError
from tests.support.migration_runner import upgrade_database_to_head


def test_provider_degradation_status_reports_documented_only_by_default() -> None:
    status = build_provider_degradation_status()

    assert status.status == "DOCUMENTED_ONLY"
    assert status.enforcement_enabled is False
    assert status.configuration_valid is True
    assert status.consecutive_failure_count == 0


def test_breaker_never_counts_failures_the_provider_did_not_cause() -> None:
    """The caller's exhausted latency budget - and every other non-provider
    condition - must not accumulate breaker strikes against an innocent
    provider (issue #244). Only provider-fault categories are tracked; this
    pins that a widened tracked set cannot land silently."""

    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60

    for category in (
        ProviderFailureCategory.REQUEST_DEADLINE_EXHAUSTED,
        ProviderFailureCategory.CAPABILITY_UNKNOWN,
        ProviderFailureCategory.KILL_SWITCH_ACTIVE,
        ProviderFailureCategory.BUDGET_EXCEEDED,
    ):
        record_provider_failure(category)

    status = build_provider_degradation_status()

    assert status.consecutive_failure_count == 0
    assert status.status != "DEGRADED_UPSTREAM"
    assert status.status != "CIRCUIT_OPEN"


def test_provider_degradation_status_reports_degraded_after_threshold() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 3
    settings.live_text_circuit_open_seconds = 60

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_RATE_LIMITED)

    status = build_provider_degradation_status()

    assert status.status == "DEGRADED_UPSTREAM"
    assert status.consecutive_failure_count == 2
    assert status.timeout_failure_count == 1
    assert status.rate_limited_failure_count == 1


def test_provider_degradation_status_reports_circuit_open_after_threshold(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 3
    settings.live_text_circuit_open_seconds = 60
    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_RATE_LIMITED)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)

    status = build_provider_degradation_status()

    assert status.status == "CIRCUIT_OPEN"
    assert status.circuit_open_remaining_seconds == 60
    assert status.last_failure_category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR

    try:
        enforce_provider_degradation_preflight()
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.CIRCUIT_OPEN
    else:
        raise AssertionError("Expected circuit-open preflight rejection")


def test_provider_degradation_status_resets_after_successful_execution(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    assert build_provider_degradation_status().status == "DEGRADED_UPSTREAM"

    record_successful_provider_execution()

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0


def test_provider_degradation_status_resets_after_circuit_cooldown(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 30
    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    assert build_provider_degradation_status().status == "CIRCUIT_OPEN"

    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now + timedelta(seconds=31),
    )

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0


def test_provider_degradation_preflight_rejects_invalid_configuration() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 1
    settings.live_text_circuit_open_seconds = -1

    status = build_provider_degradation_status()

    assert status.status == "INVALID"
    assert status.configuration_valid is False

    try:
        enforce_provider_degradation_preflight()
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.CIRCUIT_OPEN
    else:
        raise AssertionError("Expected invalid degradation configuration to block execution")


def test_provider_degradation_status_rejects_missing_circuit_threshold() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 0
    settings.live_text_circuit_open_seconds = 60

    status = build_provider_degradation_status()

    assert status.status == "INVALID"
    assert any("circuit-open failure-count threshold" in finding for finding in status.findings)


def test_provider_degradation_status_rejects_degraded_threshold_above_circuit_threshold() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 3
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60

    status = build_provider_degradation_status()

    assert status.status == "INVALID"
    assert any(
        "must not exceed the circuit-open threshold" in finding for finding in status.findings
    )


def test_provider_degradation_ignores_untracked_failure_categories() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60

    record_provider_failure(ProviderFailureCategory.CIRCUIT_OPEN)

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0


def test_provider_degradation_status_persists_circuit_state_in_sql_store_across_reset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-degradation.db'}"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    reset_provider_operations_store_cache()

    status = build_provider_degradation_status()

    assert status.status == "CIRCUIT_OPEN"
    assert status.circuit_open_remaining_seconds == 60
    assert status.timeout_failure_count == 1
    assert status.upstream_error_failure_count == 1


def test_provider_degradation_status_cooldown_recovery_survives_store_reset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-degradation.db'}"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 30
    upgrade_database_to_head(settings.database_url)

    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    reset_provider_operations_store_cache()
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now + timedelta(seconds=31),
    )

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0


# --- Reading posture must not change it (issue #248) ---------------------


def _degradation_snapshot() -> dict[str, object]:
    """Every persisted degradation row, as plain comparable data."""

    from dataclasses import asdict

    from app.services.provider_degradation_state import DEGRADATION_KEY_PREFIX

    repository = get_provider_operations_store()
    snapshot: dict[str, object] = {}
    for key in (
        DEGRADATION_KEY_PREFIX,
        f"{DEGRADATION_KEY_PREFIX}:text.openai",
        f"{DEGRADATION_KEY_PREFIX}:text.claude",
    ):
        record = repository.get_degradation_state(degradation_key=key)
        snapshot[key] = asdict(record) if record is not None else None
    return snapshot


def _enforcing_breaker() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 3
    settings.live_text_circuit_open_seconds = 60


def test_reading_posture_never_writes_whatever_the_state() -> None:
    """The acceptance condition: posture is a read.

    This case exercises the live-cooldown branch, which never wrote; it is a
    regression pin, not proof of the fix. The two branches that did write -
    an elapsed cooldown, and a failure count at or above a lowered circuit
    threshold - are covered by the two tests below, both of which fail
    against the writing resolver.
    """

    _enforcing_breaker()
    for _ in range(3):
        record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)

    for _ in range(5):
        before = _degradation_snapshot()
        assert build_provider_degradation_status().status == "CIRCUIT_OPEN"
        assert build_provider_degradation_status("text.openai").status == "CIRCUIT_OPEN"
        assert _degradation_snapshot() == before


def test_reading_an_elapsed_cooldown_reports_closed_without_writing(
    monkeypatch: MonkeyPatch,
) -> None:
    _enforcing_breaker()
    opened_at = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: opened_at)
    for _ in range(3):
        record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    assert build_provider_degradation_status().status == "CIRCUIT_OPEN"

    # Past the cooldown: the breaker has served its time.
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: opened_at + timedelta(seconds=120),
    )
    before = _degradation_snapshot()
    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0
    assert status.last_failure_category is None
    # Lifetime counters are not posture and are not zeroed by the read.
    assert status.timeout_failure_count == 3
    assert _degradation_snapshot() == before, "an elapsed cooldown was cleared by a read"

    # The next failure starts a fresh budget, and clearing happens on that write.
    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    assert build_provider_degradation_status().consecutive_failure_count == 1
    assert build_provider_degradation_status().status == "NORMAL"


def test_reading_one_identity_never_writes_another(monkeypatch: MonkeyPatch) -> None:
    """#237 fixed the attribution; this pins that a read cannot touch a
    neighbour's row at all, which is the property that made the earlier
    cross-identity write possible."""

    _enforcing_breaker()
    opened_at = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: opened_at)
    for _ in range(3):
        record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)

    before = _degradation_snapshot()
    for identity in ("text.claude", "text.openai", None):
        build_provider_degradation_status(identity)
    assert _degradation_snapshot() == before

    # The alternate has no row of its own, and reading it did not create one.
    assert (
        get_provider_operations_store().get_degradation_state(
            degradation_key="live_text_generation:text.claude"
        )
        is None
    )


def test_the_cooldown_deadline_is_stamped_once_per_crossing(monkeypatch: MonkeyPatch) -> None:
    _enforcing_breaker()
    opened_at = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: opened_at)
    for _ in range(3):
        record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)

    repository = get_provider_operations_store()
    stamped = repository.get_degradation_state(degradation_key="live_text_generation:text.openai")
    assert stamped is not None
    deadline = stamped.circuit_open_until

    # Reads do not re-stamp, and neither does the enforcing preflight while a
    # live deadline exists.
    for _ in range(3):
        build_provider_degradation_status()
    with pytest.raises(ProviderExecutionError):
        enforce_provider_degradation_preflight()
    after = repository.get_degradation_state(degradation_key="live_text_generation:text.openai")
    assert after is not None
    assert after.circuit_open_until == deadline


def test_lowering_the_threshold_opens_the_breaker_and_it_can_still_close(
    monkeypatch: MonkeyPatch,
) -> None:
    """A breaker opened by a configuration change, not by a call failing.

    It has no cooldown deadline, and while it is refusing no further failure
    can arrive to stamp one - so if nothing stamped it, it would stay open
    forever. Enforcement stamps it when it begins refusing, which is also the
    honest moment for the clock to start.
    """

    _enforcing_breaker()
    now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: now)
    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    assert build_provider_degradation_status().status == "DEGRADED_UPSTREAM"

    settings.live_text_circuit_open_failure_count_threshold = 2

    status = build_provider_degradation_status()
    assert status.status == "CIRCUIT_OPEN"
    assert status.circuit_open_remaining_seconds is None, "a read must not stamp the deadline"

    with pytest.raises(ProviderExecutionError) as exc_info:
        enforce_provider_degradation_preflight()
    assert exc_info.value.category is ProviderFailureCategory.CIRCUIT_OPEN
    assert build_provider_degradation_status().circuit_open_remaining_seconds == 60

    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow", lambda: now + timedelta(seconds=120)
    )
    assert build_provider_degradation_status().status == "NORMAL"
    enforce_provider_degradation_preflight()


def test_a_success_still_closes_an_open_breaker(monkeypatch: MonkeyPatch) -> None:
    _enforcing_breaker()
    now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: now)
    for _ in range(3):
        record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    assert build_provider_degradation_status().status == "CIRCUIT_OPEN"

    record_successful_provider_execution()

    status = build_provider_degradation_status()
    assert status.status == "NORMAL"
    assert status.circuit_open_remaining_seconds is None
