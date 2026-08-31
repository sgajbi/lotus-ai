"""Workflow-pack queue admission lease repository (issue #153, S3).

Admission capacity must bound across replicas: the count-and-insert decision
is one atomic ``try_admit`` on the repository, never a read-then-write in the
service. The memory adapter serializes under a process lock (local profile
only); the SQLAlchemy adapter serializes per policy through a guard row
locked FOR UPDATE, mirroring the provider-operations counter pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.services.workflow_pack_queue_admission_models import (
    WorkflowPackQueueAdmissionLease,
)


@dataclass(frozen=True)
class WorkflowPackAdmissionAttempt:
    admitted: bool
    active_pack_count: int
    active_lane_count: int
    # Leases this attempt reclaimed from replicas that can no longer be
    # executing them. The repository deletes; the admission service records
    # their terminal events, so a crashed item's history never stops at
    # ADMISSION_GRANTED (issue #228).
    reclaimed_leases: tuple[WorkflowPackQueueAdmissionLease, ...] = ()


class WorkflowPackAdmissionLeaseRepository(Protocol):
    def try_admit(
        self,
        lease: WorkflowPackQueueAdmissionLease,
        *,
        pack_limit: int,
        lane_limit: int,
    ) -> WorkflowPackAdmissionAttempt: ...

    def get_lease(self, queue_item_id: str) -> WorkflowPackQueueAdmissionLease | None: ...

    def delete_lease(self, queue_item_id: str) -> bool:
        """Remove one lease, reporting whether THIS call removed it."""
        ...

    def list_leases(self) -> list[WorkflowPackQueueAdmissionLease]: ...

    def clear(self) -> None: ...
