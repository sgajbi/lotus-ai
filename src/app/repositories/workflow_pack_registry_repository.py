from __future__ import annotations

from collections.abc import Sequence

from typing import Protocol

from app.contracts.workflow_packs import (
    WorkflowPackControlEventDescriptor,
    WorkflowPackRegistrationDescriptor,
)


class WorkflowPackRegistryRepository(Protocol):
    def list_registrations(self) -> list[WorkflowPackRegistrationDescriptor]:
        """List all persisted workflow-pack registrations."""

    def get_registration(
        self, *, pack_id: str, version: str
    ) -> WorkflowPackRegistrationDescriptor | None:
        """Fetch one persisted workflow-pack registration."""

    def save_registration(self, registration: WorkflowPackRegistrationDescriptor) -> None:
        """Persist one workflow-pack registration."""

    def list_control_events(
        self,
        *,
        pack_id: str | None = None,
        version: str | None = None,
        limit: int = 20,
    ) -> list[WorkflowPackControlEventDescriptor]:
        """List persisted workflow-pack control events."""

    def delete_control_events(self, event_ids: Sequence[str]) -> int:
        """Delete control-event evidence by id (issue #158, S2b)."""

    def save_control_event(self, event: WorkflowPackControlEventDescriptor) -> None:
        """Persist one workflow-pack control event."""
