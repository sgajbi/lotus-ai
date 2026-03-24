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
    assert status.split_route_degraded is False
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
    assert status.split_route_degraded is False
    assert "split-aware routing seam" in status.message


def test_retrieval_execution_status_reports_active_retrieval_plane_route(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "retrieval_split_active"
    settings.retrieval_mode = "disabled"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    status = build_retrieval_execution_status()

    assert status.owning_plane.value == "retrieval"
    assert status.route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.split_route_degraded is False
    assert "routing is active for this flow" in status.message


def test_retrieval_execution_status_reports_degraded_active_retrieval_plane_route(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "retrieval_split_active"
    settings.retrieval_mode = "disabled"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(
            governance_ready=False,
            governance_summary=["Retrieval approval evidence is stale."],
        ),
    )

    status = build_retrieval_execution_status()

    assert status.owning_plane.value == "retrieval"
    assert status.route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.split_route_degraded is True
    assert "Retrieval split activation remains configured" in status.split_route_findings[0]
    assert "currently degraded" in status.message


def test_evaluation_runtime_status_reports_active_eval_plane_route(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "retrieval_and_evals_split_active"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_eval_split_approval_gates",
        lambda: [
            SimpleNamespace(domain_label="First Use-Case Onboarding", approval_ready=True, evidence_state=SimpleNamespace(value="RUNTIME_PASS"))
        ],
    )

    status = build_evaluation_runtime_status()

    assert status.owning_plane.value == "evals"
    assert status.submission_route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.async_execution_route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.split_route_degraded is False
    assert "routing is active for this flow" in status.message


def test_evaluation_runtime_status_reports_degraded_active_eval_plane_route(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "retrieval_and_evals_split_active"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_eval_split_approval_gates",
        lambda: [
            SimpleNamespace(domain_label="First Use-Case Onboarding", approval_ready=False, evidence_state=SimpleNamespace(value="RUNTIME_FAIL"))
        ],
    )

    status = build_evaluation_runtime_status()

    assert status.owning_plane.value == "evals"
    assert status.submission_route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.async_execution_route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.split_route_degraded is True
    assert "Eval split activation remains configured" in status.split_route_findings[0]
    assert "currently degraded" in status.message
