from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.prompts import (
    PromptControlActionType,
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptManagementMode,
    PromptRolloutSelectionMode,
)
from app.db.models import (
    PromptDefinitionModel,
    PromptDefinitionVersionModel,
    PromptRolloutEventModel,
    PromptRolloutStateModel,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.services.prompt_rollout_models import (
    PromptRolloutEventRecord,
    PromptRolloutStateRecord,
)


class SqlAlchemyPromptRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_prompts(self) -> list[PromptDescriptor]:
        rollout_states = self.list_prompt_rollout_states()
        prompts: list[PromptDescriptor] = []
        for rollout_state in rollout_states:
            prompt = self.get_prompt_version(
                rollout_state.task_id, rollout_state.active_prompt_version
            )
            if prompt is not None:
                prompts.append(prompt)
        prompts.sort(key=lambda prompt: prompt.task_id)
        return prompts

    def get_prompt(self, task_id: str) -> PromptDescriptor | None:
        rollout_state = self.get_prompt_rollout_state(task_id)
        if rollout_state is None:
            return None
        return self.get_prompt_version(task_id, rollout_state.active_prompt_version)

    def list_prompt_versions(self) -> list[PromptDescriptor]:
        with self._session_factory() as session:
            prompts = session.scalars(
                select(PromptDefinitionVersionModel).order_by(
                    PromptDefinitionVersionModel.task_id,
                    PromptDefinitionVersionModel.prompt_version,
                )
            ).all()
            return [self._to_descriptor(prompt) for prompt in prompts]

    def get_prompt_version(self, task_id: str, prompt_version: str) -> PromptDescriptor | None:
        with self._session_factory() as session:
            prompt = session.get(
                PromptDefinitionVersionModel,
                {"task_id": task_id, "prompt_version": prompt_version},
            )
            if prompt is None:
                return None
            return self._to_descriptor(prompt)

    def list_prompt_rollout_states(self) -> list[PromptRolloutStateRecord]:
        with self._session_factory() as session:
            states = session.scalars(
                select(PromptRolloutStateModel).order_by(PromptRolloutStateModel.task_id)
            ).all()
            return [self._to_rollout_state(state) for state in states]

    def get_prompt_rollout_state(self, task_id: str) -> PromptRolloutStateRecord | None:
        with self._session_factory() as session:
            state = session.get(PromptRolloutStateModel, task_id)
            if state is None:
                return None
            return self._to_rollout_state(state)

    def list_prompt_rollout_events(
        self, task_id: str | None = None
    ) -> list[PromptRolloutEventRecord]:
        with self._session_factory() as session:
            statement = select(PromptRolloutEventModel).order_by(
                PromptRolloutEventModel.recorded_at,
                PromptRolloutEventModel.event_id,
            )
            if task_id is not None:
                statement = statement.where(PromptRolloutEventModel.task_id == task_id)
            events = session.scalars(statement).all()
            return [self._to_rollout_event(event) for event in events]

    def save_prompt_rollout_transition(
        self,
        *,
        rollout_state: PromptRolloutStateRecord,
        updated_prompts: list[PromptDescriptor],
        event: PromptRolloutEventRecord,
    ) -> None:
        with self._session_factory() as session:
            for prompt in updated_prompts:
                model = session.get(
                    PromptDefinitionVersionModel,
                    {"task_id": prompt.task_id, "prompt_version": prompt.prompt_version},
                )
                if model is None:
                    raise RuntimeError(
                        "Prompt rollout transition referenced a missing prompt definition version."
                    )
                model.lifecycle_status = prompt.lifecycle_status.value
                model.management_mode = prompt.management_mode.value
                model.source_reference = prompt.source_reference
                model.system_instructions = prompt.system_instructions
                model.output_contract_notes = prompt.output_contract_notes

            state_model = session.get(PromptRolloutStateModel, rollout_state.task_id)
            if state_model is None:
                raise RuntimeError("Prompt rollout transition referenced a missing rollout state.")
            state_model.active_prompt_version = rollout_state.active_prompt_version
            state_model.candidate_prompt_version = rollout_state.candidate_prompt_version
            state_model.previous_active_prompt_version = (
                rollout_state.previous_active_prompt_version
            )
            state_model.rollout_mode = rollout_state.rollout_mode.value
            state_model.runtime_mutation_enabled = rollout_state.runtime_mutation_enabled

            session.add(
                PromptRolloutEventModel(
                    event_id=event.event_id,
                    task_id=event.task_id,
                    action_type=event.action_type.value,
                    requested_by=event.requested_by,
                    approved_by=event.approved_by,
                    reason=event.reason,
                    prior_active_prompt_version=event.prior_active_prompt_version,
                    resulting_active_prompt_version=event.resulting_active_prompt_version,
                    prior_candidate_prompt_version=event.prior_candidate_prompt_version,
                    resulting_candidate_prompt_version=event.resulting_candidate_prompt_version,
                    authorization_payload=event.authorization.model_dump(mode="json"),
                    recorded_at=event.recorded_at,
                )
            )
            session.commit()

    def _to_descriptor(
        self, model: PromptDefinitionModel | PromptDefinitionVersionModel
    ) -> PromptDescriptor:
        return PromptDescriptor(
            task_id=model.task_id,
            prompt_version=model.prompt_version,
            prompt_kind=model.prompt_kind,
            lifecycle_status=PromptLifecycleStatus(model.lifecycle_status),
            management_mode=PromptManagementMode(model.management_mode),
            source_reference=model.source_reference,
            system_instructions=model.system_instructions,
            output_contract_notes=model.output_contract_notes,
        )

    def _to_rollout_state(self, model: PromptRolloutStateModel) -> PromptRolloutStateRecord:
        return PromptRolloutStateRecord(
            task_id=model.task_id,
            active_prompt_version=model.active_prompt_version,
            candidate_prompt_version=model.candidate_prompt_version,
            previous_active_prompt_version=model.previous_active_prompt_version,
            rollout_mode=PromptRolloutSelectionMode(model.rollout_mode),
            runtime_mutation_enabled=model.runtime_mutation_enabled,
        )

    def _to_rollout_event(self, model: PromptRolloutEventModel) -> PromptRolloutEventRecord:
        return PromptRolloutEventRecord(
            event_id=model.event_id,
            task_id=model.task_id,
            action_type=PromptControlActionType(model.action_type),
            requested_by=model.requested_by,
            approved_by=model.approved_by,
            reason=model.reason,
            prior_active_prompt_version=model.prior_active_prompt_version,
            resulting_active_prompt_version=model.resulting_active_prompt_version,
            prior_candidate_prompt_version=model.prior_candidate_prompt_version,
            resulting_candidate_prompt_version=model.resulting_candidate_prompt_version,
            authorization=(
                AuthorizationDecision.model_validate(model.authorization_payload)
                if model.authorization_payload is not None
                else _build_legacy_control_authorization(task_id=model.task_id)
            ),
            recorded_at=model.recorded_at,
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


def _build_legacy_control_authorization(*, task_id: str) -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="legacy-control-plane",
        capability_type=AuthorizationCapabilityType.PROMPT_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=task_id,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary=(
            "Legacy prompt control event predates explicit caller-authorization capture and is "
            "treated as a durable pre-RFC-0012 operator action."
        ),
    )
