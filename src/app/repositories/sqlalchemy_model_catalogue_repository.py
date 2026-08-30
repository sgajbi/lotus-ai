from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelCatalogueSeedSource,
    ModelLifecycleState,
)
from app.db.models import ModelCatalogueEntryModel
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
            model.approved_workflow_pack_ids = list(entry.approved_workflow_pack_ids)
            model.approval_evidence_refs = list(entry.approval_evidence_refs)
            model.approved_from_utc = entry.approved_from_utc
            model.approved_until_utc = entry.approved_until_utc
            model.seed_source = entry.seed_source.value
            model.created_at = entry.created_at
            model.last_updated_at = entry.last_updated_at
            session.commit()

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
            approved_workflow_pack_ids=list(model.approved_workflow_pack_ids),
            approval_evidence_refs=list(model.approval_evidence_refs),
            approved_from_utc=model.approved_from_utc,
            approved_until_utc=model.approved_until_utc,
            seed_source=ModelCatalogueSeedSource(model.seed_source),
            created_at=model.created_at,
            last_updated_at=model.last_updated_at,
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
