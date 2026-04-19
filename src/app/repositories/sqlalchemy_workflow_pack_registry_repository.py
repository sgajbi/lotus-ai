from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.workflow_packs import (
    WorkflowPackControlEventDescriptor,
    WorkflowPackRegistrationDescriptor,
)
from app.db.models import (
    WorkflowPackControlEventModel,
    WorkflowPackRegistrationModel,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.repositories.workflow_pack_registry_repository import WorkflowPackRegistryRepository


class SqlAlchemyWorkflowPackRegistryRepository(
    SqlAlchemyRepositoryBase, WorkflowPackRegistryRepository
):
    def __init__(
        self,
        database_url: str,
        *,
        default_registrations: list[WorkflowPackRegistrationDescriptor],
    ) -> None:
        self._database_url = database_url
        self._default_registrations = [
            registration.model_copy(deep=True) for registration in default_registrations
        ]
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)
        self._seed_defaults_if_empty()

    def list_registrations(self) -> list[WorkflowPackRegistrationDescriptor]:
        with self._session_factory() as session:
            models = session.scalars(
                select(WorkflowPackRegistrationModel).order_by(
                    WorkflowPackRegistrationModel.pack_id,
                    WorkflowPackRegistrationModel.version,
                )
            ).all()
            return [self._to_registration_descriptor(model) for model in models]

    def get_registration(
        self, *, pack_id: str, version: str
    ) -> WorkflowPackRegistrationDescriptor | None:
        with self._session_factory() as session:
            model = session.get(WorkflowPackRegistrationModel, (pack_id, version))
            if model is None:
                return None
            return self._to_registration_descriptor(model)

    def save_registration(self, registration: WorkflowPackRegistrationDescriptor) -> None:
        with self._session_factory() as session:
            session.merge(self._build_registration_model(registration))
            session.commit()

    def list_control_events(
        self,
        *,
        pack_id: str | None = None,
        version: str | None = None,
        limit: int = 20,
    ) -> list[WorkflowPackControlEventDescriptor]:
        with self._session_factory() as session:
            statement = select(WorkflowPackControlEventModel)
            if pack_id is not None:
                statement = statement.where(WorkflowPackControlEventModel.pack_id == pack_id)
            if version is not None:
                statement = statement.where(WorkflowPackControlEventModel.version == version)
            models = session.scalars(
                statement.order_by(WorkflowPackControlEventModel.recorded_at.desc())
            ).all()
            return [
                self._to_control_event_descriptor(model)
                for model in models[: max(limit, 1)]
            ]

    def save_control_event(self, event: WorkflowPackControlEventDescriptor) -> None:
        model = WorkflowPackControlEventModel(
            event_id=event.event_id,
            pack_id=event.pack_id,
            version=event.version,
            action_type=event.action_type.value,
            requested_by=event.requested_by,
            approved_by=event.approved_by,
            reason=event.reason,
            prior_registration_status=event.prior_registration_status.value,
            resulting_registration_status=event.resulting_registration_status.value,
            prior_activation_state=event.prior_activation_state.value,
            resulting_activation_state=event.resulting_activation_state.value,
            caller_app=event.caller_app,
            authorization_payload=event.authorization.model_dump(mode="json"),
            recorded_at=event.recorded_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _seed_defaults_if_empty(self) -> None:
        with self._session_factory() as session:
            has_rows = session.scalar(select(WorkflowPackRegistrationModel.pack_id).limit(1))
            if has_rows is not None:
                return
            for registration in self._default_registrations:
                session.add(self._build_registration_model(registration))
            session.commit()

    def _build_registration_model(
        self, registration: WorkflowPackRegistrationDescriptor
    ) -> WorkflowPackRegistrationModel:
        return WorkflowPackRegistrationModel(
            pack_id=registration.pack_id,
            pack_family=registration.pack_family,
            version=registration.version,
            owner_repository=registration.owner_repository,
            owner_service=registration.owner_service,
            truth_owner_services=list(registration.truth_owner_services),
            primary_use_case=registration.primary_use_case,
            workflow_authority_owner=registration.workflow_authority_owner,
            default_execution_mode=registration.default_execution_mode.value,
            definition_ref=registration.definition_ref,
            definition_refs=[
                definition_ref.model_dump(mode="json")
                for definition_ref in registration.definition_refs
            ],
            compatibility_contract_version=registration.compatibility_contract_version,
            registration_status=registration.registration_status.value,
            activation_state=registration.activation_state.value,
            registered_definition_digest=registration.registered_definition_digest,
            supported_callers=list(registration.supported_callers),
            supported_identity_classes=[
                identity_class.value for identity_class in registration.supported_identity_classes
            ],
            supported_environments=[
                environment.value for environment in registration.supported_environments
            ],
            tenant_scope=list(registration.tenant_scope),
            surface_scope=list(registration.surface_scope),
            default_rollout_stage=registration.default_rollout_stage,
            pause_state=registration.pause_state,
            supersedes=registration.supersedes,
            superseded_by=registration.superseded_by,
            registered_at=registration.registered_at,
            registered_by=registration.registered_by,
            last_activated_at=registration.last_activated_at,
            last_changed_at=registration.last_changed_at,
            status_summary=list(registration.status_summary),
        )

    def _to_registration_descriptor(
        self, model: WorkflowPackRegistrationModel
    ) -> WorkflowPackRegistrationDescriptor:
        return WorkflowPackRegistrationDescriptor.model_validate(
            {
                "pack_id": model.pack_id,
                "pack_family": model.pack_family,
                "version": model.version,
                "owner_repository": model.owner_repository,
                "owner_service": model.owner_service,
                "truth_owner_services": list(model.truth_owner_services),
                "primary_use_case": model.primary_use_case,
                "workflow_authority_owner": model.workflow_authority_owner,
                "default_execution_mode": model.default_execution_mode,
                "definition_ref": model.definition_ref,
                "definition_refs": list(model.definition_refs),
                "compatibility_contract_version": model.compatibility_contract_version,
                "registration_status": model.registration_status,
                "activation_state": model.activation_state,
                "registered_definition_digest": model.registered_definition_digest,
                "supported_callers": list(model.supported_callers),
                "supported_identity_classes": list(model.supported_identity_classes),
                "supported_environments": list(model.supported_environments),
                "tenant_scope": list(model.tenant_scope),
                "surface_scope": list(model.surface_scope),
                "default_rollout_stage": model.default_rollout_stage,
                "pause_state": model.pause_state,
                "supersedes": model.supersedes,
                "superseded_by": model.superseded_by,
                "registered_at": model.registered_at,
                "registered_by": model.registered_by,
                "last_activated_at": model.last_activated_at,
                "last_changed_at": model.last_changed_at,
                "status_summary": list(model.status_summary),
            }
        )

    def _to_control_event_descriptor(
        self, model: WorkflowPackControlEventModel
    ) -> WorkflowPackControlEventDescriptor:
        return WorkflowPackControlEventDescriptor.model_validate(
            {
                "event_id": model.event_id,
                "pack_id": model.pack_id,
                "version": model.version,
                "action_type": model.action_type,
                "requested_by": model.requested_by,
                "approved_by": model.approved_by,
                "reason": model.reason,
                "prior_registration_status": model.prior_registration_status,
                "resulting_registration_status": model.resulting_registration_status,
                "prior_activation_state": model.prior_activation_state,
                "resulting_activation_state": model.resulting_activation_state,
                "caller_app": model.caller_app,
                "authorization": (
                    AuthorizationDecision.model_validate(model.authorization_payload)
                    if model.authorization_payload is not None
                    else _build_legacy_control_authorization(model.caller_app)
                ),
                "recorded_at": model.recorded_at,
            }
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        db_path = self._database_url.removeprefix(prefix)
        if db_path == ":memory:":
            return
        path = Path(db_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)


def _build_legacy_control_authorization(caller_app: str) -> AuthorizationDecision:
    allowed = caller_app == "lotus-platform"
    return AuthorizationDecision(
        caller_app=caller_app,
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
        outcome=(
            AuthorizationOutcome.ALLOWED
            if allowed
            else AuthorizationOutcome.BLOCKED_ASYNC_CONTROL_NOT_ALLOWED
        ),
        allowed=allowed,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        summary=(
            f"Legacy workflow-pack control event for '{caller_app}' predates durable caller-policy authorization payloads."
        ),
    )
