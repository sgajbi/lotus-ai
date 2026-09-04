from __future__ import annotations

from typing import Literal, cast

from collections.abc import Sequence

from pathlib import Path

from sqlalchemy import delete, select

from app.contracts.model_catalogue import (
    ServingPolicyVersionRecord,
    ModelCapabilityDegradation,
    ModelCatalogueEntry,
    derive_candidate_identity_v2,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
    ModelLifecycleTransitionRecord,
    ModelRevisionDriftObservation,
)
from app.db.models import (
    ServingPolicyVersionModel,
    ModelCatalogueEntryModel,
    ModelCatalogueLifecycleEventModel,
    ModelRevisionDriftObservationModel,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyModelCatalogueRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_entries(self) -> list[ModelCatalogueEntry]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ModelCatalogueEntryModel).order_by(ModelCatalogueEntryModel.entry_id)
            ).all()
            return [self._to_entry(model) for model in models]

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None:
        with self._session_factory() as session:
            model = session.get(ModelCatalogueEntryModel, entry_id)
            if model is None:
                return None
            return self._to_entry(model)

    def get_entry_by_candidate_id(self, candidate_id_v2: str) -> ModelCatalogueEntry | None:
        with self._session_factory() as session:
            model = session.execute(
                select(ModelCatalogueEntryModel).where(
                    ModelCatalogueEntryModel.candidate_id_v2 == candidate_id_v2
                )
            ).scalar_one_or_none()
            if model is None:
                return None
            return self._to_entry(model)

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None:
        with self._session_factory() as session:
            model = session.get(ModelCatalogueEntryModel, entry.entry_id)
            if model is None:
                model = ModelCatalogueEntryModel(entry_id=entry.entry_id)
                session.add(model)
            model.provider_id = entry.provider_id
            model.provider_mode = entry.provider_mode
            model.model_family = entry.model_family
            model.model_revision = entry.model_revision
            model.deployment = entry.deployment
            model.sku = entry.sku
            model.lifecycle_state = entry.lifecycle_state.value
            model.revision_pinned = entry.revision_pinned
            model.modalities = list(entry.modalities)
            model.context_window_tokens = entry.context_window_tokens
            model.max_output_tokens = entry.max_output_tokens
            model.supports_structured_output = entry.supports_structured_output
            model.supports_tool_calling = entry.supports_tool_calling
            model.supports_streaming = entry.supports_streaming
            model.capability_degradations = {
                dimension: degradation.model_dump()
                for dimension, degradation in entry.capability_degradations.items()
            }
            model.approved_workflow_pack_ids = list(entry.approved_workflow_pack_ids)
            model.approval_evidence_refs = list(entry.approval_evidence_refs)
            model.approved_from_utc = entry.approved_from_utc
            model.approved_until_utc = entry.approved_until_utc
            model.seed_source = entry.seed_source.value
            model.created_at = entry.created_at
            model.last_updated_at = entry.last_updated_at
            # The write authority re-derives the canonical id: a model_copy
            # that changed identity fields but kept the original's id is
            # refused rather than stored (issue #314).
            derived_candidate_id = derive_candidate_identity_v2(
                provider_id=entry.provider_id,
                model_family=entry.model_family,
                model_revision=entry.model_revision,
                deployment=entry.deployment,
            )
            if entry.candidate_id_v2 and entry.candidate_id_v2 != derived_candidate_id:
                raise ValueError(
                    "candidate_id_v2 has drifted from the entry's structured serving "
                    f"tuple (expected '{derived_candidate_id}', got "
                    f"'{entry.candidate_id_v2}')"
                )
            model.candidate_id_v2 = derived_candidate_id
            model.deployment_key = entry.deployment or ""
            session.commit()

    def append_lifecycle_event(self, event: ModelLifecycleTransitionRecord) -> None:
        with self._session_factory() as session:
            session.add(
                ModelCatalogueLifecycleEventModel(
                    event_id=event.event_id,
                    entry_id=event.entry_id,
                    from_state=event.from_state.value,
                    to_state=event.to_state.value,
                    reason=event.reason,
                    requested_by=event.requested_by,
                    approved_by=event.approved_by,
                    approval_evidence_ref=event.approval_evidence_ref,
                    recorded_at=event.recorded_at,
                )
            )
            session.commit()

    def list_all_lifecycle_events(self, *, limit: int) -> list[ModelLifecycleTransitionRecord]:
        with self._session_factory() as session:
            models = session.execute(
                select(ModelCatalogueLifecycleEventModel)
                .order_by(ModelCatalogueLifecycleEventModel.recorded_at.desc())
                .limit(limit)
            ).scalars()
            return [
                ModelLifecycleTransitionRecord.model_validate(model, from_attributes=True)
                for model in models
            ]

    def delete_lifecycle_events(self, event_ids: Sequence[str]) -> int:
        if not event_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(ModelCatalogueLifecycleEventModel).where(
                    ModelCatalogueLifecycleEventModel.event_id.in_(list(event_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def list_all_drift_observations(self, *, limit: int) -> list[ModelRevisionDriftObservation]:
        with self._session_factory() as session:
            models = session.execute(
                select(ModelRevisionDriftObservationModel)
                .order_by(ModelRevisionDriftObservationModel.last_observed_at.desc())
                .limit(limit)
            ).scalars()
            return [self._to_drift_observation(model) for model in models]

    def delete_drift_observations(self, observation_ids: Sequence[str]) -> int:
        if not observation_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(ModelRevisionDriftObservationModel).where(
                    ModelRevisionDriftObservationModel.observation_id.in_(list(observation_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def list_lifecycle_events(self, entry_id: str) -> list[ModelLifecycleTransitionRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ModelCatalogueLifecycleEventModel)
                .where(ModelCatalogueLifecycleEventModel.entry_id == entry_id)
                .order_by(ModelCatalogueLifecycleEventModel.recorded_at.desc())
            ).all()
            return [
                ModelLifecycleTransitionRecord(
                    event_id=model.event_id,
                    entry_id=model.entry_id,
                    from_state=ModelLifecycleState(model.from_state),
                    to_state=ModelLifecycleState(model.to_state),
                    reason=model.reason,
                    requested_by=model.requested_by,
                    approved_by=model.approved_by,
                    approval_evidence_ref=model.approval_evidence_ref,
                    recorded_at=model.recorded_at,
                )
                for model in models
            ]

    def get_drift_observation(self, observation_id: str) -> ModelRevisionDriftObservation | None:
        with self._session_factory() as session:
            model = session.get(ModelRevisionDriftObservationModel, observation_id)
            if model is None:
                return None
            return self._to_drift_observation(model)

    def upsert_drift_observation(self, observation: ModelRevisionDriftObservation) -> None:
        with self._session_factory() as session:
            model = session.get(ModelRevisionDriftObservationModel, observation.observation_id)
            if model is None:
                model = ModelRevisionDriftObservationModel(
                    observation_id=observation.observation_id
                )
                session.add(model)
            model.entry_id = observation.entry_id
            model.expected_identity = observation.expected_identity
            model.observed_model_id = observation.observed_model_id
            model.revision_pinned_at_observation = observation.revision_pinned_at_observation
            model.first_observed_at = observation.first_observed_at
            model.last_observed_at = observation.last_observed_at
            model.observation_count = observation.observation_count
            session.commit()

    def list_drift_observations(self, entry_id: str) -> list[ModelRevisionDriftObservation]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ModelRevisionDriftObservationModel)
                .where(ModelRevisionDriftObservationModel.entry_id == entry_id)
                .order_by(ModelRevisionDriftObservationModel.last_observed_at.desc())
            ).all()
            return [self._to_drift_observation(model) for model in models]

    def _to_drift_observation(
        self, model: ModelRevisionDriftObservationModel
    ) -> ModelRevisionDriftObservation:
        return ModelRevisionDriftObservation(
            observation_id=model.observation_id,
            entry_id=model.entry_id,
            expected_identity=model.expected_identity,
            observed_model_id=model.observed_model_id,
            revision_pinned_at_observation=model.revision_pinned_at_observation,
            first_observed_at=model.first_observed_at,
            last_observed_at=model.last_observed_at,
            observation_count=model.observation_count,
        )

    def _to_entry(self, model: ModelCatalogueEntryModel) -> ModelCatalogueEntry:
        return ModelCatalogueEntry(
            entry_id=model.entry_id,
            provider_id=model.provider_id,
            provider_mode=model.provider_mode,
            model_family=model.model_family,
            model_revision=model.model_revision,
            deployment=model.deployment,
            sku=model.sku,
            lifecycle_state=ModelLifecycleState(model.lifecycle_state),
            revision_pinned=model.revision_pinned,
            modalities=list(model.modalities),
            context_window_tokens=model.context_window_tokens,
            max_output_tokens=model.max_output_tokens,
            supports_structured_output=model.supports_structured_output,
            supports_tool_calling=model.supports_tool_calling,
            supports_streaming=model.supports_streaming,
            capability_degradations={
                dimension: ModelCapabilityDegradation.model_validate(payload)
                for dimension, payload in (model.capability_degradations or {}).items()
            },
            approved_workflow_pack_ids=list(model.approved_workflow_pack_ids),
            approval_evidence_refs=list(model.approval_evidence_refs),
            approved_from_utc=model.approved_from_utc,
            approved_until_utc=model.approved_until_utc,
            seed_source=ModelCatalogueSeedSource(model.seed_source),
            created_at=model.created_at,
            last_updated_at=model.last_updated_at,
            # A stored canonical id is re-validated against the structured
            # fields on read: drift refuses loudly instead of being papered
            # over. A pre-backfill NULL is stamped from the tuple.
            candidate_id_v2=model.candidate_id_v2 or "",
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

    def get_current_serving_policy(self) -> ServingPolicyVersionRecord | None:
        with self._session_factory() as session:
            model = session.scalars(
                select(ServingPolicyVersionModel)
                .order_by(ServingPolicyVersionModel.version.desc())
                .limit(1)
            ).first()
            if model is None:
                return None
            return self._to_serving_policy_record(model)

    def save_serving_policy_version(self, record: ServingPolicyVersionRecord) -> None:
        with self._session_factory() as session:
            if session.get(ServingPolicyVersionModel, record.version) is not None:
                raise ValueError(f"serving policy version {record.version} already exists")
            session.add(
                ServingPolicyVersionModel(
                    version=record.version,
                    ordered_entry_ids=list(record.ordered_entry_ids),
                    action=record.action,
                    changed_entry_id=record.changed_entry_id,
                    requested_by_key_id=record.requested_by_key_id,
                    approver_key_id=record.approver_key_id,
                    governed_action_id=record.governed_action_id,
                    recorded_at=record.recorded_at,
                )
            )
            session.commit()

    def list_serving_policy_versions(self, *, limit: int) -> list[ServingPolicyVersionRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ServingPolicyVersionModel)
                .order_by(ServingPolicyVersionModel.version.desc())
                .limit(max(limit, 0))
            ).all()
            return [self._to_serving_policy_record(model) for model in models]

    def _to_serving_policy_record(
        self, model: ServingPolicyVersionModel
    ) -> ServingPolicyVersionRecord:
        return ServingPolicyVersionRecord(
            version=model.version,
            ordered_entry_ids=list(model.ordered_entry_ids),
            action=cast("Literal['IDENTITY_ADD', 'IDENTITY_REMOVE']", model.action),
            changed_entry_id=model.changed_entry_id,
            requested_by_key_id=model.requested_by_key_id,
            approver_key_id=model.approver_key_id,
            governed_action_id=model.governed_action_id,
            recorded_at=model.recorded_at,
        )
