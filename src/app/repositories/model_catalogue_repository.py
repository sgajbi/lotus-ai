from __future__ import annotations

from typing import Protocol

from app.contracts.model_catalogue import ModelCatalogueEntry


class ModelCatalogueRepository(Protocol):
    def list_entries(self) -> list[ModelCatalogueEntry]: ...

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None: ...

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None: ...
