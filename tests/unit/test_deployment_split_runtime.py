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
    assert status.route_count == 4
    assert status.routes[0].route_mode.value == "UNIFIED_INTERNAL"
    assert status.planes[0].externally_addressable is True
    assert status.planes[1].split_ready is False
    assert status.planes[2].split_ready is False


def test_deployment_split_runtime_reports_split_ready_when_production_baseline_is_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "SPLIT_READY"
    assert status.effective_stage.value == "SPLIT_READY"
    assert status.split_ready is True
    assert status.blocking_findings == []
    assert all(route.route_mode.value == "SPLIT_READY_UNIFIED" for route in status.routes)
    assert status.planes[1].split_ready is True
    assert status.planes[2].split_ready is True


def test_deployment_split_runtime_blocks_split_ready_when_production_baseline_is_not_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(
            governance_ready=False,
            governance_summary=["Production baseline governance remains blocked."],
        ),
    )

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "SPLIT_READY"
    assert status.effective_stage.value == "UNIFIED"
    assert status.split_ready is False
    assert all(route.route_mode.value == "UNIFIED_INTERNAL" for route in status.routes)
    assert status.blocking_findings[0].startswith("RFC-0020 production-baseline governance")


def test_deployment_split_runtime_reports_future_stages_as_not_yet_implemented(
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

    status = build_deployment_split_runtime_status(None)

    assert status.configured_stage.value == "RETRIEVAL_AND_EVALS_SPLIT_ACTIVE"
    assert status.effective_stage.value == "RETRIEVAL_AND_EVALS_SPLIT_ACTIVE"
    assert status.split_ready is True
    assert status.blocking_findings == []
    assert status.separate_plane_count == 2


def test_deployment_split_runtime_reports_retrieval_split_active_when_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "retrieval_split_active"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    status = build_deployment_split_runtime_status(None)

    assert status.effective_stage.value == "RETRIEVAL_SPLIT_ACTIVE"
    assert status.split_ready is True
    assert status.separate_plane_count == 1
    assert status.degraded is False
    assert status.routes[0].owning_plane.value == "retrieval"
    assert status.routes[0].route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.routes[2].route_mode.value == "SPLIT_READY_UNIFIED"


def test_deployment_split_runtime_surfaces_degraded_retrieval_split_posture(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "retrieval_split_active"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_retrieval_governance_status",
        lambda app_state: SimpleNamespace(
            governance_ready=False,
            governance_summary=["Retrieval evidence readiness remains blocked."],
        ),
    )

    status = build_deployment_split_runtime_status(None)

    assert status.effective_stage.value == "RETRIEVAL_SPLIT_ACTIVE"
    assert status.degraded is True
    assert "Retrieval split activation remains configured" in status.degraded_findings[0]
    assert status.routes[0].degraded is True
    assert status.routes[0].route_mode.value == "PLANE_SPLIT_ACTIVE"


def test_deployment_split_runtime_reports_eval_split_active_when_approval_gates_are_ready(
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
            SimpleNamespace(domain_label="Prompt Rollout", approval_ready=True, evidence_state=SimpleNamespace(value="RUNTIME_PASS"))
        ],
    )

    status = build_deployment_split_runtime_status(None)

    assert status.effective_stage.value == "RETRIEVAL_AND_EVALS_SPLIT_ACTIVE"
    assert status.separate_plane_count == 2
    assert status.degraded is False
    assert status.routes[2].owning_plane.value == "evals"
    assert status.routes[2].route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert status.routes[3].route_mode.value == "PLANE_SPLIT_ACTIVE"


def test_deployment_split_runtime_surfaces_degraded_eval_split_posture(
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
            SimpleNamespace(domain_label="Prompt Rollout", approval_ready=False, evidence_state=SimpleNamespace(value="RUNTIME_FAIL"))
        ],
    )

    status = build_deployment_split_runtime_status(None)

    assert status.effective_stage.value == "RETRIEVAL_AND_EVALS_SPLIT_ACTIVE"
    assert status.degraded is True
    assert "Eval split activation remains configured" in status.degraded_findings[0]
    assert status.routes[2].degraded is True
    assert status.routes[2].route_mode.value == "PLANE_SPLIT_ACTIVE"
