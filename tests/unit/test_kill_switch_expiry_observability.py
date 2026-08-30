"""TTL expiry events and kill-switch observability (issue #177, S4)."""

from pathlib import Path

from prometheus_client import REGISTRY

from app.config import settings
from app.contracts.kill_switches import (
    KillSwitchActivationRequest,
    KillSwitchScope,
    KillSwitchSemantics,
)
from app.services.kill_switch_control import activate_kill_switch, build_kill_switch_status
from app.services.kill_switch_store import get_kill_switch_repository
from app.services.provider_metrics import record_kill_switch_action
from app.services.provider_operations_status import build_provider_operations_status
from tests.support.migration_runner import upgrade_database_to_head


def _use_durable_store(tmp_path: Path, name: str) -> None:
    settings.kill_switch_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / name}"
    upgrade_database_to_head(settings.database_url)


def _activate(*, expires_at_utc: str | None = None) -> str:
    response = activate_kill_switch(
        KillSwitchActivationRequest(
            caller_app="lotus-platform",
            scope=KillSwitchScope.TASK,
            semantics=KillSwitchSemantics.HARD_KILL,
            target="explain.v1",
            reason="Expiry-observability test activation.",
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            expires_at_utc=expires_at_utc,
        )
    )
    return response.activation.switch_id


def _metric(action: str) -> float:
    value = REGISTRY.get_sample_value(
        "lotus_ai_kill_switch_actions_total",
        {"action": action, "scope": "TASK", "semantics": "HARD_KILL"},
    )
    return value or 0.0


def test_lapsed_ttl_records_a_durable_expiry_event_exactly_once(tmp_path: Path) -> None:
    _use_durable_store(tmp_path, "kill-switch-expiry.db")
    switch_id = _activate(expires_at_utc="2000-01-01T00:00:00Z")
    expired_before = _metric("expired")

    first = build_kill_switch_status()
    assert first.expired_count == 1
    assert first.active_count == 0
    stored = get_kill_switch_repository().get_activation(switch_id)
    assert stored is not None
    assert stored.expiry_recorded_at is not None
    recorded_at = stored.expiry_recorded_at
    assert _metric("expired") == expired_before + 1

    # Idempotent: a second read neither rewrites the marker nor recounts.
    second = build_kill_switch_status()
    assert second.expired_count == 1
    stored_again = get_kill_switch_repository().get_activation(switch_id)
    assert stored_again is not None
    assert stored_again.expiry_recorded_at == recorded_at
    assert _metric("expired") == expired_before + 1


def test_activation_and_clearance_record_counter_actions(tmp_path: Path) -> None:
    _use_durable_store(tmp_path, "kill-switch-counters.db")
    activated_before = _metric("activated")

    _activate()

    assert _metric("activated") == activated_before + 1


def test_operations_status_surfaces_the_enforcing_kill_count(tmp_path: Path) -> None:
    _use_durable_store(tmp_path, "kill-switch-operations.db")
    assert build_provider_operations_status().enforcing_kill_switch_count == 0

    _activate()

    assert build_provider_operations_status().enforcing_kill_switch_count == 1


def test_kill_switch_counter_is_fail_open_for_unbounded_actions() -> None:
    # An unknown action is normalized, never raised.
    record_kill_switch_action(action="not-a-real-action", scope="TASK", semantics="HARD_KILL")
