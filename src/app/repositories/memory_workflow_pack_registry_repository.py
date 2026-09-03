from __future__ import annotations

from collections.abc import Sequence

from app.contracts.workflow_packs import (
    WorkflowPackControlEventDescriptor,
    WorkflowPackRegistrationDescriptor,
)
from app.repositories.workflow_pack_registry_repository import WorkflowPackRegistryRepository


class InMemoryWorkflowPackRegistryRepository(WorkflowPackRegistryRepository):
    def __init__(
        self,
        *,
        registrations: list[WorkflowPackRegistrationDescriptor],
    ) -> None:
        self._registrations = {
            (registration.pack_id, registration.version): registration.model_copy(deep=True)
            for registration in registrations
        }
        self._events: dict[str, WorkflowPackControlEventDescriptor] = {}

    def list_registrations(self) -> list[WorkflowPackRegistrationDescriptor]:
        identities = sorted(self._registrations)
        return [self._registrations[identity].model_copy(deep=True) for identity in identities]

    def get_registration(
        self, *, pack_id: str, version: str
    ) -> WorkflowPackRegistrationDescriptor | None:
        registration = self._registrations.get((pack_id, version))
        if registration is None:
            return None
        return registration.model_copy(deep=True)

    def save_registration(self, registration: WorkflowPackRegistrationDescriptor) -> None:
        self._registrations[(registration.pack_id, registration.version)] = registration.model_copy(
            deep=True
        )

    def list_control_events(
        self,
        *,
        pack_id: str | None = None,
        version: str | None = None,
        limit: int = 20,
    ) -> list[WorkflowPackControlEventDescriptor]:
        events = list(self._events.values())
        if pack_id is not None:
            events = [event for event in events if event.pack_id == pack_id]
        if version is not None:
            events = [event for event in events if event.version == version]
        events.sort(key=lambda event: event.recorded_at, reverse=True)
        return [event.model_copy(deep=True) for event in events[: max(limit, 1)]]

    def delete_control_events(self, event_ids: Sequence[str]) -> int:
        deleted = 0
        for event_id in event_ids:
            if self._events.pop(event_id, None) is not None:
                deleted += 1
        return deleted

    def save_control_event(self, event: WorkflowPackControlEventDescriptor) -> None:
        self._events[event.event_id] = event.model_copy(deep=True)
