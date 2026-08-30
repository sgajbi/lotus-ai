"""Operator routing-posture inspection (issue #176, slice 4)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.config import settings
from app.contracts.kill_switches import KillSwitchActivationRecord, KillSwitchScope
from app.services.kill_switch_store import (
    get_kill_switch_repository,
    reset_kill_switch_store_cache,
)
from app.services.model_catalogue_store import reset_model_catalogue_store_cache
from app.services.routing_posture import build_routing_posture


@pytest.fixture(autouse=True)
def _fresh_stores() -> Iterator[None]:
    reset_model_catalogue_store_cache()
    reset_kill_switch_store_cache()
    yield
    reset_model_catalogue_store_cache()
    reset_kill_switch_store_cache()


def test_unconfigured_posture_reports_the_policy_and_null_candidate() -> None:
    posture = build_routing_posture()

    assert posture.policy_id == "fixed_configured_mode"
    assert posture.policy_version == "v1"
    assert posture.strategy.value == "FIXED"
    assert posture.candidate.provider_id is None
    assert posture.candidate.model_catalogue_entry_id is None
    assert posture.candidate.provider_mode == settings.provider_mode
    assert posture.enforcing_kill_switch_count == 0
    assert posture.notes


def test_configured_posture_carries_the_governed_candidate_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "provider_mode", "local_openai_compatible")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.local")
    monkeypatch.setattr(settings, "live_text_model_id", "qwen3:8b")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")

    posture = build_routing_posture()

    assert posture.candidate.provider_id == "text.local"
    assert posture.candidate.model_catalogue_entry_id == "text.local:qwen3:8b"
    assert posture.candidate.model_family == "qwen3:8b"
    assert posture.candidate.revision_pinned is False
    assert posture.candidate.lifecycle_state == "CATALOGUED"
    assert posture.degradation.status
    assert posture.quota_enforced is False
    assert posture.budget_enforced is False


def test_posture_counts_enforcing_kill_switches_and_ignores_cleared_ones() -> None:
    repository = get_kill_switch_repository()
    repository.upsert_activation(
        KillSwitchActivationRecord(
            switch_id="ksw_posture_active",
            scope=KillSwitchScope.ALL_LIVE_TEXT,
            target=None,
            reason="posture probe",
            requested_by="ops.primary@lotus",
            approved_by="ops.secondary@lotus",
            activated_at="2026-08-30T00:00:00Z",
        )
    )
    repository.upsert_activation(
        KillSwitchActivationRecord(
            switch_id="ksw_posture_cleared",
            scope=KillSwitchScope.TASK,
            target="explain.v1",
            reason="posture probe",
            requested_by="ops.primary@lotus",
            approved_by="ops.secondary@lotus",
            activated_at="2026-08-30T00:00:00Z",
            cleared_at="2026-08-30T01:00:00Z",
            cleared_by="ops.secondary@lotus",
            clear_reason="done",
        )
    )

    assert build_routing_posture().enforcing_kill_switch_count == 1
