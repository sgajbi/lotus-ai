from __future__ import annotations

from threading import RLock

from app.repositories.workflow_pack_admission_lease_repository import (
    WorkflowPackAdmissionAttempt,
)
from app.services.workflow_pack_queue_admission_models import (
    WorkflowPackQueueAdmissionLease,
)


class InMemoryWorkflowPackAdmissionLeaseRepository:
    """Process-local leases; the local-profile adapter only."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._leases: dict[str, WorkflowPackQueueAdmissionLease] = {}

    def try_admit(
        self,
        lease: WorkflowPackQueueAdmissionLease,
        *,
        pack_limit: int,
        lane_limit: int,
    ) -> WorkflowPackAdmissionAttempt:
        with self._lock:
            pack_count = sum(
                1 for item in self._leases.values() if item.policy_id == lease.policy_id
            )
            lane_count = sum(
                1
                for item in self._leases.values()
                if item.policy_id == lease.policy_id and item.lane is lease.lane
            )
            if pack_count >= pack_limit or lane_count >= lane_limit:
                return WorkflowPackAdmissionAttempt(
                    admitted=False,
                    active_pack_count=pack_count,
                    active_lane_count=lane_count,
                )
            self._leases[lease.queue_item_id] = lease
            return WorkflowPackAdmissionAttempt(
                admitted=True,
                active_pack_count=pack_count,
                active_lane_count=lane_count,
            )

    def get_lease(self, queue_item_id: str) -> WorkflowPackQueueAdmissionLease | None:
        with self._lock:
            return self._leases.get(queue_item_id)

    def delete_lease(self, queue_item_id: str) -> None:
        with self._lock:
            self._leases.pop(queue_item_id, None)

    def list_leases(self) -> list[WorkflowPackQueueAdmissionLease]:
        with self._lock:
            return list(self._leases.values())

    def clear(self) -> None:
        with self._lock:
            self._leases.clear()
