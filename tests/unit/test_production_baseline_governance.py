from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselineActivationReadinessResponse,
    ProductionBaselineDependencyDescriptor,
    ProductionBaselinePosture,
    ProductionBaselineRunbookReadinessResponse,
    ProductionBaselineRuntimeStatusResponse,
    ProductionDependencyClassification,
)
from app.services.production_baseline_activation_readiness import (
    build_production_baseline_activation_readiness,
)
from app.services.production_baseline_governance import (
    build_production_baseline_governance_status,
)
from app.services.readiness_catalog import (
    build_production_baseline_runbook_readiness,
)


def _runtime_status(
    *,
    posture: ProductionBaselinePosture,
    prod_shaped_local: bool,
    production_ready: bool,
    blocking_findings: list[str],
) -> ProductionBaselineRuntimeStatusResponse:
    return ProductionBaselineRuntimeStatusResponse(
        service="lotus-ai",
        version="0.1.0",
        posture=posture,
        prod_shaped_local=prod_shaped_local,
        production_ready=production_ready,
        dependency_count=1,
        blocked_dependency_count=int(bool(blocking_findings)),
        fallback_dependency_count=0 if production_ready else 1,
        dependencies=[
            ProductionBaselineDependencyDescriptor(
                dependency_id="database_backend",
                classification=(
                    ProductionDependencyClassification.PRODUCTION_STANDARD
                    if production_ready
                    else ProductionDependencyClassification.BLOCKED
                ),
                production_required=True,
                configured_mode="postgresql" if production_ready else "sqlite",
                detail="runtime detail",
            )
        ],
        blocking_findings=blocking_findings,
        status_summary=["runtime summary"],
    )


def test_production_baseline_activation_readiness_reports_blocking_runtime_findings(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_baseline_activation_readiness.build_production_baseline_runtime_status",
        lambda _app_state=None: _runtime_status(
            posture=ProductionBaselinePosture.LOCAL_OR_DEMO_CAPABLE,
            prod_shaped_local=False,
            production_ready=False,
            blocking_findings=["SQLite remains configured."],
        ),
    )

    readiness = build_production_baseline_activation_readiness(None)

    assert readiness.activation_ready is False
    assert readiness.production_ready is False
    assert "SQLite remains configured." in readiness.blocking_findings


def test_production_baseline_runbook_readiness_is_ready() -> None:
    readiness = build_production_baseline_runbook_readiness()

    assert readiness.runbook_ready is False
    assert readiness.completed_required_item_count == 0
    assert any(item.runbook_id == "secret_injection_boundary" for item in readiness.items)


def test_production_baseline_governance_status_composes_runtime_activation_and_runbook(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "openai"
    runtime_status = _runtime_status(
        posture=ProductionBaselinePosture.PROD_SHAPED_LOCAL,
        prod_shaped_local=True,
        production_ready=False,
        blocking_findings=["Filesystem object storage remains fallback."],
    )
    monkeypatch.setattr(
        "app.services.production_baseline_governance.build_production_baseline_runtime_status",
        lambda _app_state=None: runtime_status,
    )
    monkeypatch.setattr(
        "app.services.production_baseline_governance.build_production_baseline_activation_readiness",
        lambda _app_state=None, **_kwargs: ProductionBaselineActivationReadinessResponse(
            service="lotus-ai",
            version="0.1.0",
            posture=ProductionBaselinePosture.PROD_SHAPED_LOCAL,
            prod_shaped_local=True,
            production_ready=False,
            activation_ready=False,
            blocking_findings=["Filesystem object storage remains fallback."],
            activation_path=["move object storage to production backend"],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_governance.build_production_baseline_runbook_readiness",
        lambda: ProductionBaselineRunbookReadinessResponse(
            service="lotus-ai",
            version="0.1.0",
            runbook_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_governance.build_provider_governance_status",
        lambda: SimpleNamespace(governance_ready=False),
    )
    monkeypatch.setattr(
        "app.services.production_baseline_governance.build_first_use_case_governance_status",
        lambda: SimpleNamespace(governance_ready=False),
    )

    governance = build_production_baseline_governance_status(None)

    assert governance.governance_ready is False
    assert governance.runtime_status.posture is ProductionBaselinePosture.PROD_SHAPED_LOCAL
    assert governance.provider_governance_ready is False
    assert governance.first_use_case_governance_ready is False
    assert governance.blocking_area_count == 2
    assert len(governance.dependent_rollout_findings) == 2
