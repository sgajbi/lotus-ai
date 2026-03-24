from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.deployment_split_runtime import build_deployment_split_runtime_status


def test_deployment_split_runtime_defaults_to_unified() -> None:
    settings.deployment_split_stage = "unified"

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "UNIFIED"
    assert status.effective_stage.value == "UNIFIED"
    assert status.split_ready is False
    assert status.front_door_plane.value == "runtime"
    assert status.plane_count == 3
    assert status.separate_plane_count == 0
    assert status.planes[0].externally_addressable is True
    assert status.planes[1].split_ready is False
    assert status.planes[2].split_ready is False


def test_deployment_split_runtime_reports_split_ready_when_production_baseline_is_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    monkeypatch.setattr(
        "app.services.deployment_split_runtime.build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "SPLIT_READY"
    assert status.effective_stage.value == "SPLIT_READY"
    assert status.split_ready is True
    assert status.blocking_findings == []
    assert status.planes[1].split_ready is True
    assert status.planes[2].split_ready is True


def test_deployment_split_runtime_blocks_split_ready_when_production_baseline_is_not_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    monkeypatch.setattr(
        "app.services.deployment_split_runtime.build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(
            governance_ready=False,
            governance_summary=["Production baseline governance remains blocked."],
        ),
    )

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "SPLIT_READY"
    assert status.effective_stage.value == "UNIFIED"
    assert status.split_ready is False
    assert status.blocking_findings[0].startswith("RFC-0020 production-baseline governance")


def test_deployment_split_runtime_reports_future_stages_as_not_yet_implemented() -> None:
    settings.deployment_split_stage = "retrieval_split_active"

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "RETRIEVAL_SPLIT_ACTIVE"
    assert status.effective_stage.value == "UNIFIED"
    assert status.split_ready is False
    assert "not yet implemented" in status.blocking_findings[0]
