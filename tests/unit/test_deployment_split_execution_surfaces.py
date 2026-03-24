from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.eval_status import build_evaluation_runtime_status
from app.services.retrieval_execution_status import build_retrieval_execution_status


def test_retrieval_execution_status_reports_split_ready_route_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    settings.retrieval_mode = "disabled"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    status = build_retrieval_execution_status()

    assert status.owning_plane.value == "runtime"
    assert status.route_mode.value == "SPLIT_READY_UNIFIED"
    assert status.rollback_target_stage.value == "UNIFIED"
    assert "split-aware routing seam" in status.message


def test_evaluation_runtime_status_reports_split_ready_route_modes(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    status = build_evaluation_runtime_status()

    assert status.owning_plane.value == "runtime"
    assert status.submission_route_mode.value == "SPLIT_READY_UNIFIED"
    assert status.async_execution_route_mode.value == "SPLIT_READY_UNIFIED"
    assert status.rollback_target_stage.value == "UNIFIED"
    assert "split-aware routing seam" in status.message
