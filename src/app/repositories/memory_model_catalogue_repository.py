from __future__ import annotations

from app.contracts.model_catalogue import ModelCatalogueEntry


class InMemoryModelCatalogueRepository:
    def __init__(self) -> None:
        self._entries: dict[str, ModelCatalogueEntry] = {}

    def list_entries(self) -> list[ModelCatalogueEntry]:
        return [self._entries[entry_id].model_copy(deep=True) for entry_id in sorted(self._entries)]

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None:
        entry = self._entries.get(entry_id)
        return entry.model_copy(deep=True) if entry is not None else None

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None:
        self._entries[entry.entry_id] = entry.model_copy(deep=True)
