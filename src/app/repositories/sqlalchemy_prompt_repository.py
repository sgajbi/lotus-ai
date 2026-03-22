from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.contracts.prompts import PromptDescriptor
from app.db.models import PromptDefinitionModel


class SqlAlchemyPromptRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def list_prompts(self) -> list[PromptDescriptor]:
        with self._session_factory() as session:
            prompts = session.scalars(
                select(PromptDefinitionModel).order_by(PromptDefinitionModel.task_id)
            ).all()
            return [self._to_descriptor(prompt) for prompt in prompts]

    def get_prompt(self, task_id: str) -> PromptDescriptor | None:
        with self._session_factory() as session:
            prompt = session.get(PromptDefinitionModel, task_id)
            if prompt is None:
                return None
            return self._to_descriptor(prompt)

    def _to_descriptor(self, model: PromptDefinitionModel) -> PromptDescriptor:
        return PromptDescriptor(
            task_id=model.task_id,
            prompt_version=model.prompt_version,
            prompt_kind=model.prompt_kind,
            system_instructions=model.system_instructions,
            output_contract_notes=model.output_contract_notes,
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
