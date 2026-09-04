from __future__ import annotations

from collections.abc import Sequence

from typing import Protocol

from app.contracts.model_catalogue import (
    ModelCatalogueEntry,
    ModelLifecycleTransitionRecord,
    ModelRevisionDriftObservation,
    ServingPolicyVersionRecord,
)


class ModelCatalogueRepository(Protocol):
    def list_entries(self) -> list[ModelCatalogueEntry]: ...

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None: ...

    def get_entry_by_candidate_id(self, candidate_id_v2: str) -> ModelCatalogueEntry | None: ...

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None: ...

    def get_current_serving_policy(self) -> ServingPolicyVersionRecord | None:
        """The operative (highest-version) serving policy, if one exists."""
        ...

    def save_serving_policy_version(self, record: ServingPolicyVersionRecord) -> None:
        """Append one immutable policy version; a duplicate version number is refused."""
        ...

    def list_serving_policy_versions(self, *, limit: int) -> list[ServingPolicyVersionRecord]:
        """Policy versions, newest first."""
        ...

    def append_lifecycle_event(self, event: ModelLifecycleTransitionRecord) -> None: ...

    def list_lifecycle_events(self, entry_id: str) -> list[ModelLifecycleTransitionRecord]: ...

    def list_all_lifecycle_events(self, *, limit: int) -> list[ModelLifecycleTransitionRecord]:
        """List lifecycle events across every entry (lifecycle engine read)."""
        ...

    def delete_lifecycle_events(self, event_ids: Sequence[str]) -> int:
        """Delete lifecycle-event evidence by id (issue #158, S2b)."""
        ...

    def get_drift_observation(
        self, observation_id: str
    ) -> ModelRevisionDriftObservation | None: ...

    def upsert_drift_observation(self, observation: ModelRevisionDriftObservation) -> None: ...

    def list_drift_observations(self, entry_id: str) -> list[ModelRevisionDriftObservation]: ...

    def list_all_drift_observations(self, *, limit: int) -> list[ModelRevisionDriftObservation]:
        """List drift observations across every entry (lifecycle engine read)."""
        ...

    def delete_drift_observations(self, observation_ids: Sequence[str]) -> int:
        """Delete drift-observation evidence by id (issue #158, S2b)."""
        ...
