from __future__ import annotations

from collections.abc import Sequence

from app.contracts.model_catalogue import (
    ServingPolicyVersionRecord,
    ModelCatalogueEntry,
    ModelLifecycleTransitionRecord,
    ModelRevisionDriftObservation,
)


class InMemoryModelCatalogueRepository:
    def __init__(self) -> None:
        self._entries: dict[str, ModelCatalogueEntry] = {}
        self._lifecycle_events: list[ModelLifecycleTransitionRecord] = []
        self._drift_observations: dict[str, ModelRevisionDriftObservation] = {}
        self._serving_policy_versions: dict[int, ServingPolicyVersionRecord] = {}

    def list_entries(self) -> list[ModelCatalogueEntry]:
        return [self._entries[entry_id].model_copy(deep=True) for entry_id in sorted(self._entries)]

    def get_entry(self, entry_id: str) -> ModelCatalogueEntry | None:
        entry = self._entries.get(entry_id)
        return entry.model_copy(deep=True) if entry is not None else None

    def get_entry_by_candidate_id(self, candidate_id_v2: str) -> ModelCatalogueEntry | None:
        for entry in self._entries.values():
            if entry.candidate_id_v2 == candidate_id_v2:
                return entry.model_copy(deep=True)
        return None

    def upsert_entry(self, entry: ModelCatalogueEntry) -> None:
        self._entries[entry.entry_id] = _with_verified_canonical_identity(entry)

    def append_lifecycle_event(self, event: ModelLifecycleTransitionRecord) -> None:
        self._lifecycle_events.append(event.model_copy(deep=True))

    def list_all_lifecycle_events(self, *, limit: int) -> list[ModelLifecycleTransitionRecord]:
        events = sorted(self._lifecycle_events, key=lambda e: e.recorded_at, reverse=True)
        return [event.model_copy(deep=True) for event in events[:limit]]

    def delete_lifecycle_events(self, event_ids: Sequence[str]) -> int:
        wanted = set(event_ids)
        before = len(self._lifecycle_events)
        self._lifecycle_events = [e for e in self._lifecycle_events if e.event_id not in wanted]
        return before - len(self._lifecycle_events)

    def list_all_drift_observations(self, *, limit: int) -> list[ModelRevisionDriftObservation]:
        observations = sorted(
            self._drift_observations.values(), key=lambda o: o.last_observed_at, reverse=True
        )
        return [observation.model_copy(deep=True) for observation in observations[:limit]]

    def delete_drift_observations(self, observation_ids: Sequence[str]) -> int:
        deleted = 0
        for observation_id in observation_ids:
            if self._drift_observations.pop(observation_id, None) is not None:
                deleted += 1
        return deleted

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

    def get_current_serving_policy(self) -> ServingPolicyVersionRecord | None:
        if not self._serving_policy_versions:
            return None
        return self._serving_policy_versions[max(self._serving_policy_versions)].model_copy(
            deep=True
        )

    def save_serving_policy_version(self, record: ServingPolicyVersionRecord) -> None:
        if record.version in self._serving_policy_versions:
            raise ValueError(f"serving policy version {record.version} already exists")
        self._serving_policy_versions[record.version] = record.model_copy(deep=True)

    def list_serving_policy_versions(self, *, limit: int) -> list[ServingPolicyVersionRecord]:
        versions = sorted(self._serving_policy_versions, reverse=True)[: max(limit, 0)]
        return [
            self._serving_policy_versions[version].model_copy(deep=True) for version in versions
        ]


def _with_verified_canonical_identity(entry: ModelCatalogueEntry) -> ModelCatalogueEntry:
    """Refuse a canonical id that has drifted from the structured tuple.

    ``model_copy(update=...)`` bypasses pydantic validators, so a copy that
    changed identity fields would otherwise carry the ORIGINAL entry's
    canonical id into the store (issue #314). The write authority re-derives
    and refuses a stale non-empty id loudly; an empty id is stamped.
    """

    from app.contracts.model_catalogue import derive_candidate_identity_v2

    derived = derive_candidate_identity_v2(
        provider_id=entry.provider_id,
        model_family=entry.model_family,
        model_revision=entry.model_revision,
        deployment=entry.deployment,
    )
    if entry.candidate_id_v2 and entry.candidate_id_v2 != derived:
        raise ValueError(
            "candidate_id_v2 has drifted from the entry's structured serving tuple "
            f"(expected '{derived}', got '{entry.candidate_id_v2}'); model_copy that "
            "changes identity fields must reset candidate_id_v2 to ''"
        )
    return entry.model_copy(deep=True, update={"candidate_id_v2": derived})
