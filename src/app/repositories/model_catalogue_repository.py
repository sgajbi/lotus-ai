from __future__ import annotations

from typing import Protocol

from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelLifecycleTransitionRecord,
    ModelRevisionDriftObservation,
)


class ModelCatalogueRepository(Protocol):
    def list_entries(self) -> list[ModelCatalogueEntry]: ...

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None: ...

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None: ...

    def append_lifecycle_event(self, event: ModelLifecycleTransitionRecord) -> None: ...

    def list_lifecycle_events(self, entry_id: str) -> list[ModelLifecycleTransitionRecord]: ...

    def get_drift_observation(
        self, observation_id: str
    ) -> ModelRevisionDriftObservation | None: ...

    def upsert_drift_observation(self, observation: ModelRevisionDriftObservation) -> None: ...

    def list_drift_observations(self, entry_id: str) -> list[ModelRevisionDriftObservation]: ...
