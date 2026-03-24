from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.deployment_split_routing import build_split_route_descriptors


def test_build_split_route_descriptors_reports_unified_routes_by_default() -> None:
    settings.deployment_split_stage = "unified"

    routes = build_split_route_descriptors(None)

    assert len(routes) == 4
    assert all(route.owning_plane.value == "runtime" for route in routes)
    assert all(route.route_mode.value == "UNIFIED_INTERNAL" for route in routes)


def test_build_split_route_descriptors_reports_split_ready_unified_routes(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.deployment_split_stage = "split_ready"
    monkeypatch.setattr(
        "app.services.deployment_split_shared._build_production_baseline_governance_status",
        lambda app_state: SimpleNamespace(governance_ready=True, governance_summary=[]),
    )

    routes = build_split_route_descriptors(None)

    assert len(routes) == 4
    assert all(route.owning_plane.value == "runtime" for route in routes)
    assert all(route.route_mode.value == "SPLIT_READY_UNIFIED" for route in routes)
    assert all(route.rollback_target_stage.value == "UNIFIED" for route in routes)


def test_build_split_route_descriptors_reports_retrieval_plane_active_when_enabled(
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

    routes = build_split_route_descriptors(None)

    assert routes[0].owning_plane.value == "retrieval"
    assert routes[0].route_mode.value == "PLANE_SPLIT_ACTIVE"
    assert routes[1].owning_plane.value == "retrieval"
    assert routes[2].route_mode.value == "SPLIT_READY_UNIFIED"


def test_build_split_route_descriptors_marks_retrieval_routes_degraded_when_governance_drifts(
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
            governance_summary=["Retrieval runbook readiness remains blocked."],
        ),
    )

    routes = build_split_route_descriptors(None)

    assert routes[0].degraded is True
    assert routes[0].degraded_findings[0].startswith("Retrieval split activation remains configured")
    assert routes[1].degraded is True
    assert routes[2].degraded is False
