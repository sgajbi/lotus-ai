from pathlib import Path

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackControlActionType,
    WorkflowPackControlEventDescriptor,
    WorkflowPackRegistrationStatus,
)
from app.db.models import WorkflowPackControlEventModel
from app.repositories.memory_workflow_pack_registry_repository import (
    InMemoryWorkflowPackRegistryRepository,
)
from app.repositories.sqlalchemy_workflow_pack_registry_repository import (
    SqlAlchemyWorkflowPackRegistryRepository,
)
from app.services.workflow_pack_registry_store import (
    get_workflow_pack_registry_store,
    reset_workflow_pack_registry_store_cache,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.config import settings
from tests.support.migration_runner import upgrade_database_to_head


def _authorization() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-platform",
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=None,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary="Allowed workflow-pack control decision.",
    )


def test_workflow_pack_registry_store_returns_cached_memory_repository_and_resets() -> None:
    settings.workflow_pack_registry_store_mode = "memory"
    reset_workflow_pack_registry_store_cache()

    first_repository = get_workflow_pack_registry_store()

    assert isinstance(first_repository, InMemoryWorkflowPackRegistryRepository)
    assert first_repository is get_workflow_pack_registry_store()

    reset_workflow_pack_registry_store_cache()

    assert get_workflow_pack_registry_store() is not first_repository


def test_workflow_pack_registry_store_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'workflow-pack-registry-store.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_workflow_pack_registry_store_cache()

    repository = get_workflow_pack_registry_store()

    assert isinstance(repository, SqlAlchemyWorkflowPackRegistryRepository)
    registrations = repository.list_registrations()
    assert [f"{registration.pack_id}@{registration.version}" for registration in registrations] == [
        "advisor_brief.pack@v1",
        "advisor_brief.pack@v2",
        "outcome_review_narrative.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]


def test_workflow_pack_registry_store_rejects_invalid_configuration() -> None:
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_workflow_pack_registry_store_cache()

    try:
        get_workflow_pack_registry_store()
    except RuntimeError as exc:
        assert "WORKFLOW_PACK_REGISTRY_STORE_MODE=sqlalchemy" in str(exc)
    else:
        raise AssertionError("Expected missing database configuration to fail")

    settings.workflow_pack_registry_store_mode = "unsupported"

    try:
        get_workflow_pack_registry_store()
    except RuntimeError as exc:
        assert "Unsupported workflow-pack registry store mode" in str(exc)
    else:
        raise AssertionError("Expected unsupported workflow-pack registry store mode to fail")


def test_sqlalchemy_workflow_pack_registry_repository_filters_control_events(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-registry-store.db'}"
    upgrade_database_to_head(database_url)
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    repository = SqlAlchemyWorkflowPackRegistryRepository(
        database_url,
        default_registrations=[registration],
    )

    assert repository.get_registration(pack_id="missing.pack", version="v1") is None

    repository.save_control_event(
        WorkflowPackControlEventDescriptor(
            event_id="evt-advisor",
            pack_id="advisor_brief.pack",
            version="v1",
            action_type=WorkflowPackControlActionType.PAUSE,
            requested_by="ops.user@lotus",
            approved_by="ops.approver@lotus",
            reason="Pause for review.",
            prior_registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            resulting_registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            prior_activation_state=WorkflowPackActivationState.ACTIVE,
            resulting_activation_state=WorkflowPackActivationState.PAUSED,
            caller_app="lotus-platform",
            authorization=_authorization(),
            recorded_at="2026-04-21T00:00:00Z",
        )
    )
    repository.save_control_event(
        WorkflowPackControlEventDescriptor(
            event_id="evt-workspace",
            pack_id="workspace_rationale.pack",
            version="v1",
            action_type=WorkflowPackControlActionType.RESUME,
            requested_by="ops.user@lotus",
            approved_by="ops.approver@lotus",
            reason="Resume after review.",
            prior_registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            resulting_registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            prior_activation_state=WorkflowPackActivationState.PAUSED,
            resulting_activation_state=WorkflowPackActivationState.ACTIVE,
            caller_app="lotus-platform",
            authorization=_authorization(),
            recorded_at="2026-04-21T00:01:00Z",
        )
    )

    filtered = repository.list_control_events(pack_id="advisor_brief.pack", version="v1")

    assert [event.event_id for event in filtered] == ["evt-advisor"]


def test_sqlalchemy_workflow_pack_registry_repository_preserves_existing_rows_and_legacy_auth(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-registry-store.db'}"
    upgrade_database_to_head(database_url)
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    first_repository = SqlAlchemyWorkflowPackRegistryRepository(
        database_url,
        default_registrations=[registration],
    )
    first_repository.save_registration(
        registration.model_copy(update={"status_summary": ["custom operator summary"]})
    )

    second_repository = SqlAlchemyWorkflowPackRegistryRepository(
        database_url,
        default_registrations=[registration],
    )

    restored_registration = second_repository.get_registration(
        pack_id="advisor_brief.pack",
        version="v1",
    )
    assert restored_registration is not None
    assert restored_registration.status_summary == ["custom operator summary"]

    with second_repository._session_factory() as session:
        session.add(
            WorkflowPackControlEventModel(
                event_id="evt-legacy",
                pack_id="advisor_brief.pack",
                version="v1",
                action_type=WorkflowPackControlActionType.PAUSE.value,
                requested_by="legacy.user@lotus",
                approved_by="legacy.approver@lotus",
                reason="Legacy event.",
                prior_registration_status=WorkflowPackRegistrationStatus.REGISTERED.value,
                resulting_registration_status=WorkflowPackRegistrationStatus.REGISTERED.value,
                prior_activation_state=WorkflowPackActivationState.ACTIVE.value,
                resulting_activation_state=WorkflowPackActivationState.PAUSED.value,
                caller_app="legacy-tooling",
                authorization_payload=None,
                recorded_at="2026-04-21T00:02:00Z",
            )
        )
        session.commit()

    legacy_event = second_repository.list_control_events(limit=1)[0]

    assert legacy_event.event_id == "evt-legacy"
    assert legacy_event.authorization.allowed is False


def test_sqlalchemy_workflow_pack_registry_repository_sqlite_parent_handling(
    tmp_path: Path,
) -> None:
    repository = object.__new__(SqlAlchemyWorkflowPackRegistryRepository)

    repository._database_url = "postgresql://example"
    repository._ensure_sqlite_parent_directory()

    repository._database_url = "sqlite:///:memory:"
    repository._ensure_sqlite_parent_directory()

    relative_db_path = tmp_path / "relative" / "workflow-pack-registry.db"
    repository._database_url = f"sqlite:///{relative_db_path}"
    repository._ensure_sqlite_parent_directory()

    assert relative_db_path.parent.is_dir()
