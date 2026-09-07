"""Worker-owned health contract for the dedicated async worker (issue #369).

The worker runs no HTTP server. It inherited the API image's HEALTHCHECK, which
probes `http://127.0.0.1:8140/health/live` on a port the worker never binds, so
every probe failed and Docker reported a permanently unhealthy worker while the
worker was executing jobs correctly. A false unhealthy is not a safe default: it
is indistinguishable from a real failure, so it hides one.

The fix is not a dummy HTTP server. The worker writes a liveness marker each
loop cycle recording what it just observed, and the health command reads that
marker in a separate process. The marker is evidence the worker produced about
itself, so it cannot report healthy unless the loop actually ran.

Everything here is fail-closed. A missing, unreadable, stale, or foreign marker
is unhealthy - never "assume fine". The one thing this must never do is return
healthy without evidence, because a reassuring readiness signal with nothing
behind it is the defect this issue exists to remove, one layer up.

API and worker semantics are deliberately different and are not interchangeable:

- API `/health/ready` answers "can this process serve HTTP requests now".
- Worker health answers "did this worker's loop run recently AND reach the queue
  backend it needs to do any work at all".

A worker with an unreachable queue is not degraded, it is unable to serve, so it
reports unhealthy rather than a reassuring partial state.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

MARKER_VERSION = "lotus-ai.worker-liveness.v1"


class WorkerHealthReason:
    """Reason codes. Distinct per cause so an operator is told what to fix."""

    HEALTHY = "WORKER_HEALTHY"
    MARKER_MISSING = "WORKER_LIVENESS_MARKER_MISSING"
    MARKER_UNREADABLE = "WORKER_LIVENESS_MARKER_UNREADABLE"
    MARKER_FOREIGN = "WORKER_LIVENESS_MARKER_FOREIGN_WORKER"
    MARKER_STALE = "WORKER_LIVENESS_STALE"
    QUEUE_BACKEND_UNAVAILABLE = "WORKER_QUEUE_BACKEND_UNAVAILABLE"
    RUNTIME_CONFIG_INVALID = "WORKER_RUNTIME_CONFIG_INVALID"


@dataclass(frozen=True)
class WorkerHealthVerdict:
    healthy: bool
    reason_code: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {"healthy": self.healthy, "reason_code": self.reason_code, "detail": self.detail}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _marker_path() -> Path:
    return Path(settings.async_worker_liveness_path)


def record_worker_liveness(
    *,
    worker_id: str,
    queue_backend_available: bool,
    queue_backend_id: str,
    cutover_state: str,
    drain_enabled: bool,
    recorded_at: datetime | None = None,
) -> None:
    """Write the marker for the cycle that just completed.

    Written atomically via a temporary file and `os.replace`, so a health command
    reading concurrently sees either the previous cycle's marker or this one and
    never a half-written file. A truncated marker would be read as unreadable and
    report a healthy worker as unhealthy, which is the failure this issue is
    about pointing the other way.

    Failures to write are deliberately NOT swallowed by the caller into silence:
    the loop logs and continues, and the marker simply ages out, which the health
    command reports as stale. A worker that cannot record evidence about itself
    must not be able to keep claiming health.
    """

    marker = {
        "marker_version": MARKER_VERSION,
        "worker_id": worker_id,
        "recorded_at": (recorded_at or _now()).isoformat(),
        "queue_backend_available": queue_backend_available,
        "queue_backend_id": queue_backend_id,
        "cutover_state": cutover_state,
        "drain_enabled": drain_enabled,
    }
    path = _marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            json.dump(marker, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    except BaseException:
        # Never leave a temp file behind to accumulate in the data volume.
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def evaluate_worker_health(
    *,
    expected_worker_id: str | None = None,
    now: datetime | None = None,
) -> WorkerHealthVerdict:
    """Decide worker health from the marker alone. Fail closed."""

    worker_id = expected_worker_id or settings.async_worker_id
    path = _marker_path()

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_MISSING,
            detail=(
                f"No worker liveness marker at {path}. The worker has not completed a "
                "loop cycle, so there is no evidence it can serve."
            ),
        )
    except OSError as exc:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_UNREADABLE,
            detail=f"Worker liveness marker at {path} could not be read: {exc}.",
        )

    try:
        marker = json.loads(raw)
    except json.JSONDecodeError as exc:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_UNREADABLE,
            detail=f"Worker liveness marker at {path} is not valid JSON: {exc}.",
        )
    if not isinstance(marker, dict) or marker.get("marker_version") != MARKER_VERSION:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_UNREADABLE,
            detail=(
                f"Worker liveness marker at {path} is not a {MARKER_VERSION} record. "
                "An unrecognised marker is treated as no evidence."
            ),
        )

    marker_worker_id = marker.get("worker_id")
    if marker_worker_id != worker_id:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_FOREIGN,
            detail=(
                f"Worker liveness marker was written by {marker_worker_id!r}, not "
                f"{worker_id!r}. One worker's liveness never answers for another's."
            ),
        )

    recorded_at_raw = marker.get("recorded_at")
    try:
        recorded_at = datetime.fromisoformat(str(recorded_at_raw))
    except ValueError:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_UNREADABLE,
            detail=f"Worker liveness marker timestamp {recorded_at_raw!r} is not ISO-8601.",
        )
    if recorded_at.tzinfo is None:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_UNREADABLE,
            detail=(
                f"Worker liveness marker timestamp {recorded_at_raw!r} carries no timezone, "
                "so its age cannot be established."
            ),
        )

    max_age = settings.async_worker_liveness_max_age_seconds
    age_seconds = ((now or _now()) - recorded_at).total_seconds()
    # A marker from the future is as untrustworthy as a stale one: it would let a
    # stopped worker keep reporting healthy for as long as the skew lasts.
    if age_seconds > max_age or age_seconds < -max_age:
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.MARKER_STALE,
            detail=(
                f"Worker liveness marker is {age_seconds:.1f}s old against a bound of "
                f"{max_age}s. The worker is stopped, stalled, or its clock disagrees."
            ),
        )

    if marker.get("cutover_state") != "dedicated_workers_active":
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.RUNTIME_CONFIG_INVALID,
            detail=(
                f"Worker runtime posture is {marker.get('cutover_state')!r}. A dedicated "
                "worker that is not in dedicated_workers_active consumes nothing, so it "
                "must not report healthy."
            ),
        )

    if not marker.get("queue_backend_available"):
        return WorkerHealthVerdict(
            healthy=False,
            reason_code=WorkerHealthReason.QUEUE_BACKEND_UNAVAILABLE,
            detail=(
                f"Worker could not reach queue backend "
                f"{marker.get('queue_backend_id')!r} on its last cycle. It is running "
                "but unable to serve, which is unhealthy rather than degraded."
            ),
        )

    return WorkerHealthVerdict(
        healthy=True,
        reason_code=WorkerHealthReason.HEALTHY,
        detail=(
            f"Worker {worker_id} completed a cycle {age_seconds:.1f}s ago and reached "
            f"queue backend {marker.get('queue_backend_id')!r}."
        ),
    )


__all__ = [
    "MARKER_VERSION",
    "WorkerHealthReason",
    "WorkerHealthVerdict",
    "evaluate_worker_health",
    "record_worker_liveness",
]
