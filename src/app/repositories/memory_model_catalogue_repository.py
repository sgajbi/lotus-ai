from __future__ import annotations

from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelLifecycleTransitionRecord,
    ModelRevisionDriftObservation,
)


class InMemoryModelCatalogueRepository:
    def __init__(self) -> None:
        self._entries: dict[str, ModelCatalogueEntry] = {}
        self._lifecycle_events: list[ModelLifecycleTransitionRecord] = []
        self._drift_observations: dict[str, ModelRevisionDriftObservation] = {}

    def list_entries(self) -> list[ModelCatalogueEntry]:
        return [self._entries[entry_id].model_copy(deep=True) for entry_id in sorted(self._entries)]

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None:
        entry = self._entries.get(entry_id)
        return entry.model_copy(deep=True) if entry is not None else None

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None:
        self._entries[entry.entry_id] = entry.model_copy(deep=True)

    def append_lifecycle_event(self, event: ModelLifecycleTransitionRecord) -> None:
        self._lifecycle_events.append(event.model_copy(deep=True))

    def list_lifecycle_events(self, entry_id: str) -> list[ModelLifecycleTransitionRecord]:
        return sorted(
            (
                event.model_copy(deep=True)
                for event in self._lifecycle_events
                if event.entry_id == entry_id
            ),
            key=lambda event: event.recorded_at,
            reverse=True,
        )

    def get_drift_observation(self, observation_id: str) -> ModelRevisionDriftObservation | None:
        observation = self._drift_observations.get(observation_id)
        return observation.model_copy(deep=True) if observation is not None else None

    def upsert_drift_observation(self, observation: ModelRevisionDriftObservation) -> None:
        self._drift_observations[observation.observation_id] = observation.model_copy(deep=True)

    def list_drift_observations(self, entry_id: str) -> list[ModelRevisionDriftObservation]:
        return sorted(
            (
                observation.model_copy(deep=True)
                for observation in self._drift_observations.values()
                if observation.entry_id == entry_id
            ),
            key=lambda observation: observation.last_observed_at,
            reverse=True,
        )
