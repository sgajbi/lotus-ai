from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselinePosture,
    ProductionBaselineRuntimeStatusResponse,
)
from app.contracts.production_go_live import (
    ProductionGoLiveDomainDescriptor,
    ProductionGoLiveDomainStatus,
)
from app.services.production_go_live_runtime import build_production_go_live_runtime_status


def test_build_production_go_live_runtime_status_distinguishes_platform_and_use_case_states() -> (
    None
):
    status = build_production_go_live_runtime_status()

    assert status.service == "lotus-ai"
    assert status.technically_running is True
    assert status.production_capable is False
    assert status.platform_state.value == "TECHNICALLY_RUNNING"
    assert status.use_case_state.value == "PRE_PROD_VALIDATION"
    assert status.platform_production_approved is False
    assert status.use_case_production_approved is False
    assert status.provider_freeze_state.value == "NOT_APPLICABLE"
    assert status.provider_rollback_state.value == "NOT_APPLICABLE"
    assert status.provider_rollback_target_state is None
    assert any(domain.domain_id == "managed_secret_posture" for domain in status.approval_domains)
    assert any(domain.domain_id == "managed_object_storage" for domain in status.approval_domains)


def test_build_production_go_live_runtime_status_blocks_platform_approval_on_managed_domains() -> (
    None
):
    status = build_production_go_live_runtime_status()
    domain_by_id = {domain.domain_id: domain for domain in status.approval_domains}

    assert domain_by_id["managed_secret_posture"].required_for_platform_approval is True
    assert domain_by_id["managed_secret_posture"].status.value == "BLOCKED"
    assert domain_by_id["managed_object_storage"].required_for_platform_approval is True
    assert domain_by_id["managed_object_storage"].status.value == "BLOCKED"
    assert status.blocked_domain_count == 2


def test_build_production_go_live_runtime_uses_artifact_governance_surface_for_object_storage() -> (
    None
):
    status = build_production_go_live_runtime_status()
    domain_by_id = {domain.domain_id: domain for domain in status.approval_domains}

    assert (
        domain_by_id["managed_object_storage"].review_surface
        == "/platform/artifacts/governance-status"
    )
    assert any(
        phrase in domain_by_id["managed_object_storage"].detail
        for phrase in (
            "Artifact payload storage",
            "Filesystem artifact payload storage",
            "Artifact object-store durability",
        )
    )


def test_build_production_go_live_runtime_can_become_production_capable_but_not_approved(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.secret_source_mode = "local_or_unspecified"
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_production_baseline_runtime_status",
        lambda app_state: ProductionBaselineRuntimeStatusResponse(
            service="lotus-ai",
            version="0.1.0",
            posture=ProductionBaselinePosture.PROD_SHAPED_LOCAL,
            prod_shaped_local=True,
            production_ready=False,
            dependency_count=0,
            blocked_dependency_count=0,
            fallback_dependency_count=0,
            dependencies=[],
            blocking_findings=[],
            status_summary=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_managed_object_storage_approval_domain",
        lambda: ProductionGoLiveDomainDescriptor(
            domain_id="managed_object_storage",
            status=ProductionGoLiveDomainStatus.APPROVED,
            required_for_platform_approval=True,
            configured_mode="s3",
            review_surface="/platform/artifacts/governance-status",
            detail="ready",
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_managed_secret_approval_domain",
        lambda: ProductionGoLiveDomainDescriptor(
            domain_id="managed_secret_posture",
            status=ProductionGoLiveDomainStatus.BLOCKED,
            required_for_platform_approval=True,
            configured_mode="local_or_unspecified",
            review_surface="/platform/production-baseline/runtime-status",
            detail="blocked",
        ),
    )

    status = build_production_go_live_runtime_status()

    assert status.production_capable is True
    assert status.platform_state.value == "PRODUCTION_CAPABLE"
    assert status.platform_production_approved is False


def test_build_production_go_live_runtime_treats_provider_governance_as_platform_blocker_when_live_provider_is_configured(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "openai"
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_production_baseline_runtime_status",
        lambda app_state: ProductionBaselineRuntimeStatusResponse(
            service="lotus-ai",
            version="0.1.0",
            posture=ProductionBaselinePosture.PRODUCTION_READY,
            prod_shaped_local=True,
            production_ready=True,
            dependency_count=0,
            blocked_dependency_count=0,
            fallback_dependency_count=0,
            dependencies=[],
            blocking_findings=[],
            status_summary=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_managed_object_storage_approval_domain",
        lambda: ProductionGoLiveDomainDescriptor(
            domain_id="managed_object_storage",
            status=ProductionGoLiveDomainStatus.APPROVED,
            required_for_platform_approval=True,
            configured_mode="s3",
            review_surface="/platform/artifacts/governance-status",
            detail="ready",
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_managed_secret_approval_domain",
        lambda: ProductionGoLiveDomainDescriptor(
            domain_id="managed_secret_posture",
            status=ProductionGoLiveDomainStatus.APPROVED,
            required_for_platform_approval=True,
            configured_mode="deployment_managed",
            review_surface="/platform/production-baseline/runtime-status",
            detail="ready",
        ),
    )

    status = build_production_go_live_runtime_status()
    domain_by_id = {domain.domain_id: domain for domain in status.approval_domains}

    assert status.production_capable is True
    assert status.platform_production_approved is False
    assert status.platform_state.value == "PRODUCTION_CAPABLE"
    assert domain_by_id["live_provider_governance"].required_for_platform_approval is True


def test_build_production_go_live_runtime_reports_provider_freeze_when_allowlisted_disabled() -> (
    None
):
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    status = build_production_go_live_runtime_status()

    assert status.provider_freeze_state.value == "FROZEN"
    assert status.provider_rollback_state.value == "COMPLETED"
    assert status.provider_rollback_target_state == "ALLOWLISTED_DISABLED"


def test_build_production_go_live_runtime_can_report_platform_and_use_case_production_approval(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "ROLLED_OUT"
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_production_baseline_runtime_status",
        lambda app_state: ProductionBaselineRuntimeStatusResponse(
            service="lotus-ai",
            version="0.1.0",
            posture=ProductionBaselinePosture.PRODUCTION_READY,
            prod_shaped_local=True,
            production_ready=True,
            dependency_count=0,
            blocked_dependency_count=0,
            fallback_dependency_count=0,
            dependencies=[],
            blocking_findings=[],
            status_summary=[],
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_managed_object_storage_approval_domain",
        lambda: ProductionGoLiveDomainDescriptor(
            domain_id="managed_object_storage",
            status=ProductionGoLiveDomainStatus.APPROVED,
            required_for_platform_approval=True,
            configured_mode="s3",
            review_surface="/platform/artifacts/governance-status",
            detail="ready",
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_managed_secret_approval_domain",
        lambda: ProductionGoLiveDomainDescriptor(
            domain_id="managed_secret_posture",
            status=ProductionGoLiveDomainStatus.APPROVED,
            required_for_platform_approval=True,
            configured_mode="deployment_managed",
            review_surface="/platform/production-baseline/runtime-status",
            detail="ready",
        ),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": True})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_first_use_case_governance_status",
        lambda: type(
            "UseCaseGovernance",
            (),
            {
                "active_production_ready": True,
                "governance_ready": True,
                "rollout_stage": type("RolloutStage", (), {"value": "ACTIVE_PRODUCTION"})(),
            },
        )(),
    )

    status = build_production_go_live_runtime_status()
    domain_by_id = {domain.domain_id: domain for domain in status.approval_domains}

    assert status.platform_state.value == "PLATFORM_PRODUCTION_APPROVED"
    assert status.use_case_state.value == "USE_CASE_PRODUCTION_APPROVED"
    assert status.platform_production_approved is True
    assert status.use_case_production_approved is True
    assert status.provider_freeze_state.value == "ACTIVE"
    assert status.provider_rollback_state.value == "AVAILABLE"
    assert status.provider_rollback_target_state == "ALLOWLISTED_DISABLED"
    assert domain_by_id["live_provider_governance"].status.value == "APPROVED"
    assert domain_by_id["downstream_use_case_production"].status.value == "APPROVED"
    assert status.blocked_domain_count == 0


def test_build_production_go_live_runtime_marks_review_required_rollout_for_unapproved_live_provider(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_provider_governance_status",
        lambda: type("ProviderGovernance", (), {"governance_ready": False})(),
    )
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_first_use_case_governance_status",
        lambda: type(
            "UseCaseGovernance",
            (),
            {
                "active_production_ready": False,
                "governance_ready": True,
                "rollout_stage": type("RolloutStage", (), {"value": "LIMITED_ROLLOUT"})(),
            },
        )(),
    )

    status = build_production_go_live_runtime_status()

    assert status.provider_freeze_state.value == "REVIEW_REQUIRED"
    assert status.provider_rollback_state.value == "RECOMMENDED"
    assert status.provider_rollback_target_state == "ALLOWLISTED_DISABLED"
    assert status.use_case_state.value == "LIMITED_ROLLOUT_ONLY"


def test_build_production_go_live_runtime_uses_informational_use_case_domain_for_limited_rollout_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.production_go_live_runtime.build_first_use_case_governance_status",
        lambda: type(
            "UseCaseGovernance",
            (),
            {
                "active_production_ready": False,
                "governance_ready": True,
                "rollout_stage": type("RolloutStage", (), {"value": "LIMITED_ROLLOUT"})(),
            },
        )(),
    )

    status = build_production_go_live_runtime_status()
    domain_by_id = {domain.domain_id: domain for domain in status.approval_domains}

    assert domain_by_id["downstream_use_case_production"].status.value == "INFORMATIONAL"
    assert status.use_case_state.value == "LIMITED_ROLLOUT_ONLY"
