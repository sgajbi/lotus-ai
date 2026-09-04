from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.production_go_live import (
    ProductionGoLiveActivationReadinessResponse,
    ProductionGoLiveFreezeState,
    ProductionGoLiveRunbookReadinessItem,
    ProductionGoLiveRunbookReadinessResponse,
    ProductionGoLiveRuntimeStatusResponse,
    ProductionGoLiveUseCaseApprovalItem,
    ProductionGoLiveUseCaseApprovalResponse,
    ProductionGoLiveUseCaseApprovalState,
)
from app.services.production_go_live_activation_readiness import (
    build_production_go_live_activation_readiness,
)
from app.services.production_go_live_governance import (
    build_production_go_live_governance_status,
)
from app.services.readiness_catalog import build_production_go_live_runbook_readiness
from app.services.production_go_live_use_case_approval import (
    build_production_go_live_use_case_approval,
)


def test_production_go_live_activation_readiness_reports_provider_review_required() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.secret_source_mode = "local_or_unspecified"

    readiness = build_production_go_live_activation_readiness()

    assert readiness.activation_ready is False
    assert readiness.runtime_status.provider_freeze_state.value == "REVIEW_REQUIRED"
    assert readiness.runtime_status.provider_rollback_state.value == "RECOMMENDED"
    assert readiness.runtime_status.provider_rollback_target_state == "ALLOWLISTED_DISABLED"
    assert any(
        "allowlisted-disabled provider rollout target" in item.lower()
        for item in readiness.blocking_findings
    )


def test_production_go_live_runbook_readiness_tracks_provider_runbook_dependency() -> None:
    readiness = build_production_go_live_runbook_readiness()

    assert readiness.runbook_ready is False
    assert readiness.required_item_count == 4
    # Honest catalog states (issue #284): documented posture is
    # DOCUMENTED_ONLY, never READY, so nothing counts as completed until a
    # control is actually enforced.
    assert readiness.completed_required_item_count == 0
    assert any(
        item.runbook_id == "production_go_live_provider_freeze_and_rollback"
        for item in readiness.items
    )
    alignment = next(
        item
        for item in readiness.items
        if item.runbook_id == "production_go_live_provider_incident_alignment"
    )
    # Derived, not declared: the provider runbook surface is not enforced,
    # so the alignment item resolves PARTIAL through its catalog hook.
    assert alignment.status == "PARTIAL"
    assert len(readiness.go_live_checklist) == 4


def test_production_go_live_governance_composes_runtime_activation_and_runbook() -> None:
    governance = build_production_go_live_governance_status()

    assert governance.governance_ready is False
    assert governance.runtime_status.platform_state.value == "TECHNICALLY_RUNNING"
    assert governance.activation_readiness.activation_ready is False
    assert governance.runbook_readiness.runbook_ready is False
    assert governance.use_case_approval.approval_state.value == "PRE_PROD_VALIDATION"
    assert governance.use_case_approval.active_production_ready is False
    assert governance.provider_governance_ready is False
    assert governance.go_live_decision == "BLOCKED"
    assert governance.blocking_area_count >= 3


def test_production_go_live_use_case_approval_reports_limited_rollout_ready_before_platform_approval(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_first_use_case_governance_status",
        lambda: type(
            "UseCaseGovernance",
            (),
            {
                "governance_ready": True,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_first_use_case_runtime_status",
        lambda: type(
            "UseCaseRuntime",
            (),
            {
                "use_case_id": "lotus_performance.analytics_commentary.v1",
                "downstream_app": "lotus-performance",
                "capability_pack_id": "analytics_commentary.pack.v1",
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_capability_pack_governance_status",
        lambda pack_id: type("PackGovernance", (), {"governance_ready": True})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": True})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_production_go_live_runtime_status",
        lambda app_state: type(
            "GoLiveRuntime",
            (),
            {
                "platform_production_approved": False,
                "provider_freeze_state": type("FreezeState", (), {"value": "NOT_APPLICABLE"})(),
            },
        )(),
    )

    approval = build_production_go_live_use_case_approval()

    assert approval.limited_rollout_ready is True
    assert approval.active_production_ready is False
    assert approval.approval_state.value == "LIMITED_ROLLOUT_READY"


def test_production_go_live_activation_readiness_can_become_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_activation_readiness.build_production_go_live_runtime_status",
        lambda app_state: ProductionGoLiveRuntimeStatusResponse.model_validate(
            {
                "service": "lotus-ai",
                "version": "0.1.0",
                "platform_state": "PLATFORM_PRODUCTION_APPROVED",
                "use_case_state": "PRE_PROD_VALIDATION",
                "technically_running": True,
                "production_capable": True,
                "platform_production_approved": True,
                "use_case_production_approved": False,
                "provider_freeze_state": "ACTIVE",
                "provider_rollback_state": "AVAILABLE",
                "provider_rollback_target_state": "ALLOWLISTED_DISABLED",
                "approval_domain_count": 0,
                "blocked_domain_count": 0,
                "approval_domains": [],
                "blocking_findings": [],
                "status_summary": ["ready"],
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_activation_readiness.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": True})(),
    )

    readiness = build_production_go_live_activation_readiness()

    assert readiness.activation_ready is True
    assert readiness.blocking_findings == []


def test_production_go_live_use_case_approval_can_report_production_approved(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_first_use_case_governance_status",
        lambda: type(
            "UseCaseGovernance",
            (),
            {
                "governance_ready": True,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_first_use_case_runtime_status",
        lambda: type(
            "UseCaseRuntime",
            (),
            {
                "use_case_id": "lotus_performance.analytics_commentary.v1",
                "downstream_app": "lotus-performance",
                "capability_pack_id": "analytics_commentary.pack.v1",
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_capability_pack_governance_status",
        lambda pack_id: type("PackGovernance", (), {"governance_ready": True})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": True})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_production_go_live_runtime_status",
        lambda app_state: type(
            "GoLiveRuntime",
            (),
            {
                "platform_production_approved": True,
                "provider_freeze_state": ProductionGoLiveFreezeState.ACTIVE,
            },
        )(),
    )

    approval = build_production_go_live_use_case_approval()

    assert approval.active_production_ready is True
    assert approval.approval_state.value == "PRODUCTION_APPROVED"
    assert approval.completed_required_item_count == approval.required_item_count


def test_production_go_live_use_case_approval_can_report_production_blocked_after_limited_rollout(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_first_use_case_governance_status",
        lambda: type(
            "UseCaseGovernance",
            (),
            {
                "governance_ready": True,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_first_use_case_runtime_status",
        lambda: type(
            "UseCaseRuntime",
            (),
            {
                "use_case_id": "lotus_performance.analytics_commentary.v1",
                "downstream_app": "lotus-performance",
                "capability_pack_id": "analytics_commentary.pack.v1",
            },
        )(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_capability_pack_governance_status",
        lambda pack_id: type("PackGovernance", (), {"governance_ready": True})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": False})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_use_case_approval.build_production_go_live_runtime_status",
        lambda app_state: type(
            "GoLiveRuntime",
            (),
            {
                "platform_production_approved": True,
                "provider_freeze_state": ProductionGoLiveFreezeState.ACTIVE,
            },
        )(),
    )

    approval = build_production_go_live_use_case_approval()

    assert approval.limited_rollout_ready is True
    assert approval.active_production_ready is False
    assert approval.approval_state.value == "PRODUCTION_BLOCKED"


def test_production_go_live_governance_can_report_production_approved(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_runtime_status",
        lambda app_state: ProductionGoLiveRuntimeStatusResponse.model_validate(
            {
                "service": "lotus-ai",
                "version": "0.1.0",
                "platform_state": "PLATFORM_PRODUCTION_APPROVED",
                "use_case_state": "USE_CASE_PRODUCTION_APPROVED",
                "technically_running": True,
                "production_capable": True,
                "platform_production_approved": True,
                "use_case_production_approved": True,
                "provider_freeze_state": "ACTIVE",
                "provider_rollback_state": "AVAILABLE",
                "provider_rollback_target_state": "ALLOWLISTED_DISABLED",
                "approval_domain_count": 0,
                "blocked_domain_count": 0,
                "approval_domains": [],
                "blocking_findings": [],
                "status_summary": ["ready"],
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_activation_readiness",
        lambda app_state, **_kwargs: ProductionGoLiveActivationReadinessResponse.model_validate(
            {
                "service": "lotus-ai",
                "version": "0.1.0",
                "runtime_status": {
                    "service": "lotus-ai",
                    "version": "0.1.0",
                    "platform_state": "PLATFORM_PRODUCTION_APPROVED",
                    "use_case_state": "USE_CASE_PRODUCTION_APPROVED",
                    "technically_running": True,
                    "production_capable": True,
                    "platform_production_approved": True,
                    "use_case_production_approved": True,
                    "provider_freeze_state": "ACTIVE",
                    "provider_rollback_state": "AVAILABLE",
                    "provider_rollback_target_state": "ALLOWLISTED_DISABLED",
                    "approval_domain_count": 0,
                    "blocked_domain_count": 0,
                    "approval_domains": [],
                    "blocking_findings": [],
                    "status_summary": ["ready"],
                },
                "provider_governance_ready": True,
                "activation_ready": True,
                "blocking_findings": [],
                "activation_path": ["ready"],
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_runbook_readiness",
        lambda: ProductionGoLiveRunbookReadinessResponse(
            service="lotus-ai",
            version="0.1.0",
            runbook_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[
                ProductionGoLiveRunbookReadinessItem(
                    runbook_id="go_live",
                    status="READY",
                    required_for_activation=True,
                    notes="ready",
                )
            ],
            go_live_checklist=["ready"],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_use_case_approval",
        lambda app_state, **_kwargs: ProductionGoLiveUseCaseApprovalResponse(
            service="lotus-ai",
            version="0.1.0",
            use_case_id="lotus_performance.analytics_commentary.v1",
            downstream_app="lotus-performance",
            capability_pack_id="analytics_commentary.pack.v1",
            approval_state=ProductionGoLiveUseCaseApprovalState.PRODUCTION_APPROVED,
            limited_rollout_ready=True,
            active_production_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[
                ProductionGoLiveUseCaseApprovalItem(
                    item_id="approval",
                    status="READY",
                    required_for_activation=True,
                    notes="ready",
                )
            ],
            status_summary=["ready"],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": True})(),
    )

    governance = build_production_go_live_governance_status()

    assert governance.governance_ready is True
    assert governance.go_live_decision == "PRODUCTION_APPROVED"
    assert governance.blocking_area_count == 0


def test_production_go_live_governance_can_report_limited_rollout_only(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_runtime_status",
        lambda app_state: ProductionGoLiveRuntimeStatusResponse.model_validate(
            {
                "service": "lotus-ai",
                "version": "0.1.0",
                "platform_state": "PRODUCTION_CAPABLE",
                "use_case_state": "LIMITED_ROLLOUT_ONLY",
                "technically_running": True,
                "production_capable": True,
                "platform_production_approved": False,
                "use_case_production_approved": False,
                "provider_freeze_state": "REVIEW_REQUIRED",
                "provider_rollback_state": "RECOMMENDED",
                "provider_rollback_target_state": "ALLOWLISTED_DISABLED",
                "approval_domain_count": 0,
                "blocked_domain_count": 0,
                "approval_domains": [],
                "blocking_findings": [],
                "status_summary": ["ready"],
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_activation_readiness",
        lambda app_state, **_kwargs: ProductionGoLiveActivationReadinessResponse.model_validate(
            {
                "service": "lotus-ai",
                "version": "0.1.0",
                "runtime_status": {
                    "service": "lotus-ai",
                    "version": "0.1.0",
                    "platform_state": "PRODUCTION_CAPABLE",
                    "use_case_state": "LIMITED_ROLLOUT_ONLY",
                    "technically_running": True,
                    "production_capable": True,
                    "platform_production_approved": False,
                    "use_case_production_approved": False,
                    "provider_freeze_state": "REVIEW_REQUIRED",
                    "provider_rollback_state": "RECOMMENDED",
                    "provider_rollback_target_state": "ALLOWLISTED_DISABLED",
                    "approval_domain_count": 0,
                    "blocked_domain_count": 0,
                    "approval_domains": [],
                    "blocking_findings": [],
                    "status_summary": ["ready"],
                },
                "provider_governance_ready": True,
                "activation_ready": False,
                "blocking_findings": ["blocked"],
                "activation_path": ["ready"],
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_runbook_readiness",
        lambda: ProductionGoLiveRunbookReadinessResponse(
            service="lotus-ai",
            version="0.1.0",
            runbook_ready=True,
            required_item_count=1,
            completed_required_item_count=1,
            items=[
                ProductionGoLiveRunbookReadinessItem(
                    runbook_id="go_live",
                    status="READY",
                    required_for_activation=True,
                    notes="ready",
                )
            ],
            go_live_checklist=["ready"],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_production_go_live_use_case_approval",
        lambda app_state, **_kwargs: ProductionGoLiveUseCaseApprovalResponse(
            service="lotus-ai",
            version="0.1.0",
            use_case_id="lotus_performance.analytics_commentary.v1",
            downstream_app="lotus-performance",
            capability_pack_id="analytics_commentary.pack.v1",
            approval_state=ProductionGoLiveUseCaseApprovalState.LIMITED_ROLLOUT_READY,
            limited_rollout_ready=True,
            active_production_ready=False,
            required_item_count=1,
            completed_required_item_count=0,
            items=[
                ProductionGoLiveUseCaseApprovalItem(
                    item_id="approval",
                    status="NOT_READY",
                    required_for_activation=True,
                    notes="blocked",
                )
            ],
            status_summary=["blocked"],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_governance.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": True})(),
    )

    governance = build_production_go_live_governance_status()

    assert governance.governance_ready is False
    assert governance.go_live_decision == "LIMITED_ROLLOUT_ONLY"
    assert governance.blocking_area_count == 2
