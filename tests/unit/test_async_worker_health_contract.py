"""Worker health must be worker-owned evidence, and must be able to fail (#369).

The worker inherited the API image's HEALTHCHECK, which probes
http://127.0.0.1:8140/health/live on a port the worker never binds. Every probe
failed, so Docker reported a permanently unhealthy worker while it executed jobs
correctly - a signal that could not distinguish a working worker from a broken
one, in either direction.

These tests hold the two halves that matter together: a worker with real
evidence reports healthy, and every way of having no evidence reports unhealthy.
A readiness check that cannot fail is the defect, so each negative case here is
as load-bearing as the positive one.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import settings
from app.contracts.async_runtime import AsyncCutoverState
from app.services.async_worker_health import (
    MARKER_VERSION,
    WorkerHealthReason,
    evaluate_worker_health,
    record_worker_liveness,
)

WORKER_ID = "lotus-ai-worker-test"


@pytest.fixture
def marker_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "worker-liveness.json"
    monkeypatch.setattr(settings, "async_worker_liveness_path", str(path))
    monkeypatch.setattr(settings, "async_worker_liveness_max_age_seconds", 60)
    monkeypatch.setattr(settings, "async_worker_id", WORKER_ID)
    return path


def _real_posture() -> object:
    """Posture carrying the REAL enum member.

    A stand-in object is not equal to AsyncCutoverState.DEDICATED_WORKERS_ACTIVE,
    so process_next_async_delivery returns at the posture check and the code
    under test never runs - the test then passes without exercising anything.
    """

    return type("Posture", (), {"cutover_state": AsyncCutoverState.DEDICATED_WORKERS_ACTIVE})()


def _record(**overrides: object) -> None:
    payload: dict[str, object] = {
        "worker_id": WORKER_ID,
        "queue_backend_available": True,
        "queue_backend_id": "redis_queue",
        "cutover_state": "dedicated_workers_active",
        "drain_enabled": False,
    }
    payload.update(overrides)
    record_worker_liveness(**payload)  # type: ignore[arg-type]


def test_a_worker_that_completed_a_cycle_and_reached_its_queue_is_healthy(
    marker_path: Path,
) -> None:
    _record()

    verdict = evaluate_worker_health()

    assert verdict.healthy is True
    assert verdict.reason_code == WorkerHealthReason.HEALTHY


def test_a_worker_that_has_never_completed_a_cycle_is_unhealthy(marker_path: Path) -> None:
    """The state at container start, and the one a dummy HTTP probe hid.

    No marker means no evidence. Reporting healthy here would be exactly the
    reassuring-without-evidence signal this issue exists to remove.
    """

    assert not marker_path.exists()

    verdict = evaluate_worker_health()

    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.MARKER_MISSING


def test_a_stopped_or_stalled_worker_is_unhealthy_once_its_marker_ages_out(
    marker_path: Path,
) -> None:
    """The deterministic negative case for a worker that is no longer looping."""

    stale = datetime.now(timezone.utc) - timedelta(
        seconds=settings.async_worker_liveness_max_age_seconds + 1
    )
    _record(recorded_at=stale)

    verdict = evaluate_worker_health()

    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.MARKER_STALE


def test_a_marker_inside_the_bound_is_still_healthy(marker_path: Path) -> None:
    """Divergence half for staleness: the bound must not refuse a live worker.

    Without this, a check that called everything stale would satisfy the test
    above while reporting every healthy worker as unhealthy - which is the
    original defect, reintroduced through its own fix.
    """

    recent = datetime.now(timezone.utc) - timedelta(
        seconds=settings.async_worker_liveness_max_age_seconds - 5
    )
    _record(recorded_at=recent)

    assert evaluate_worker_health().healthy is True


def test_an_unreachable_queue_backend_is_unhealthy_not_degraded(marker_path: Path) -> None:
    """A worker that cannot reach its queue can do no work at all.

    This is the evaluation condition from the issue: sever the required queue
    dependency and health must become unhealthy, not a reassuring partial state.
    """

    _record(queue_backend_available=False)

    verdict = evaluate_worker_health()

    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.QUEUE_BACKEND_UNAVAILABLE


def test_an_invalid_runtime_posture_is_unhealthy(marker_path: Path) -> None:
    """A dedicated worker not in dedicated_workers_active consumes nothing."""

    _record(cutover_state="in_process_only")

    verdict = evaluate_worker_health()

    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.RUNTIME_CONFIG_INVALID


def test_another_workers_marker_never_answers_for_this_worker(marker_path: Path) -> None:
    """Liveness is per-worker evidence, not a shared "some worker is alive" flag."""

    _record(worker_id="lotus-ai-worker-somebody-else")

    verdict = evaluate_worker_health()

    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.MARKER_FOREIGN


@pytest.mark.parametrize(
    ("content", "case"),
    [
        ("", "empty"),
        ("{not json", "truncated"),
        (json.dumps({"marker_version": "something-else", "worker_id": WORKER_ID}), "wrong version"),
        (json.dumps([1, 2, 3]), "not an object"),
    ],
)
def test_an_unreadable_marker_is_unhealthy_rather_than_ignored(
    marker_path: Path, content: str, case: str
) -> None:
    """Fail closed on anything that is not a marker this code wrote."""

    marker_path.write_text(content, encoding="utf-8")

    verdict = evaluate_worker_health()

    assert verdict.healthy is False, case
    assert verdict.reason_code == WorkerHealthReason.MARKER_UNREADABLE, case


def test_a_marker_dated_in_the_future_is_unhealthy(marker_path: Path) -> None:
    """Otherwise a stopped worker keeps reporting healthy for the whole skew."""

    future = datetime.now(timezone.utc) + timedelta(
        seconds=settings.async_worker_liveness_max_age_seconds + 30
    )
    _record(recorded_at=future)

    assert evaluate_worker_health().healthy is False


def test_a_naive_timestamp_is_unhealthy_because_its_age_is_unknowable(
    marker_path: Path,
) -> None:
    marker_path.write_text(
        json.dumps(
            {
                "marker_version": MARKER_VERSION,
                "worker_id": WORKER_ID,
                "recorded_at": datetime.now().isoformat(),
                "queue_backend_available": True,
                "queue_backend_id": "redis_queue",
                "cutover_state": "dedicated_workers_active",
                "drain_enabled": False,
            }
        ),
        encoding="utf-8",
    )

    verdict = evaluate_worker_health()

    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.MARKER_UNREADABLE


def test_the_marker_write_is_atomic_and_leaves_no_partial_file(marker_path: Path) -> None:
    """A truncated marker would report a healthy worker as unhealthy.

    Written via a temp file and os.replace, so a concurrent reader sees either
    the previous cycle's marker or this one. Asserted by checking no temporary
    files survive in the directory, which is what a non-atomic write leaks.
    """

    for _ in range(3):
        _record()

    siblings = [entry.name for entry in marker_path.parent.iterdir()]
    assert siblings == [marker_path.name], siblings
    assert json.loads(marker_path.read_text(encoding="utf-8"))["worker_id"] == WORKER_ID


def test_the_worker_loop_actually_records_liveness_each_cycle(
    marker_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The module being correct is not the same as the loop calling it.

    A health contract wired to nothing reads as satisfied: the evaluator would
    keep reporting MARKER_MISSING forever and an operator would read that as a
    broken worker rather than a missing call. So this drives the real loop and
    asserts the marker appears, rather than calling record_worker_liveness
    directly - which would pass with the loop integration deleted.
    """

    from app.services import async_worker_fleet

    monkeypatch.setattr(
        async_worker_fleet,
        "process_next_async_delivery",
        lambda **_: None,
    )
    assert not marker_path.exists()

    async_worker_fleet.run_dedicated_worker_loop(
        worker_id=WORKER_ID,
        timeout_seconds=0,
        idle_sleep_seconds=0.0,
        max_cycles=1,
    )

    assert marker_path.exists(), "the worker loop completed a cycle and recorded nothing"
    recorded = json.loads(marker_path.read_text(encoding="utf-8"))
    assert recorded["worker_id"] == WORKER_ID


def test_an_idle_worker_still_reports_healthy(
    marker_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker with no jobs is correctly idle, not stopped.

    The durable per-job heartbeat could not carry this contract: it is written
    on job leases, so an idle worker writes none and would report unhealthy -
    reproducing the original false-unhealthy defect through a different route.
    """

    from app.services import async_worker_fleet

    monkeypatch.setattr(async_worker_fleet, "process_next_async_delivery", lambda **_: None)
    monkeypatch.setattr(
        async_worker_fleet,
        "get_async_runtime_posture",
        lambda: _real_posture(),
    )
    monkeypatch.setattr(
        async_worker_fleet,
        "get_async_delivery_queue",
        lambda: type(
            "Q",
            (),
            {
                "snapshot": lambda self: type(
                    "S", (), {"backend_available": True, "backend_id": "redis_queue"}
                )()
            },
        )(),
    )

    async_worker_fleet.run_dedicated_worker_loop(
        worker_id=WORKER_ID, timeout_seconds=0, idle_sleep_seconds=0.0, max_cycles=1
    )

    assert evaluate_worker_health().healthy is True


def test_a_queue_outage_makes_the_worker_unhealthy_rather_than_killing_it(
    marker_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A health contract cannot detect what kills it first.

    Observed on a real Docker run while proving this issue: stopping Redis
    raised redis.exceptions.ConnectionError straight out of dequeue, the loop
    had no handler, and the worker container exited 1. The health status did
    flip to unhealthy, but by process death rather than by the contract - so
    WORKER_QUEUE_BACKEND_UNAVAILABLE was unreachable in practice, which is a
    dead branch in the very check this issue adds.

    The worker must stay up, report the outage attributably, and be able to
    recover when the backend returns.
    """

    from app.services import async_worker_fleet

    class _DeadQueue:
        def dequeue(self, *, timeout_seconds: int) -> None:
            raise ConnectionError("Error 111 connecting to redis:6379. Connection refused.")

        def snapshot(self) -> object:
            return type("S", (), {"backend_available": False, "backend_id": "redis_queue"})()

    monkeypatch.setattr(async_worker_fleet, "get_async_delivery_queue", lambda: _DeadQueue())
    monkeypatch.setattr(
        async_worker_fleet,
        "get_async_runtime_posture",
        lambda: _real_posture(),
    )
    monkeypatch.setattr(async_worker_fleet.settings, "async_worker_drain_enabled", False)

    # The loop must complete the cycle rather than propagating the outage.
    async_worker_fleet.run_dedicated_worker_loop(
        worker_id=WORKER_ID, timeout_seconds=0, idle_sleep_seconds=0.0, max_cycles=1
    )

    verdict = evaluate_worker_health()
    assert verdict.healthy is False
    assert verdict.reason_code == WorkerHealthReason.QUEUE_BACKEND_UNAVAILABLE


def test_job_execution_failures_are_not_swallowed_by_the_queue_outage_handler(
    marker_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Divergence half: the handler must catch the dequeue, not everything.

    A try/except wide enough to cover dispatch would hide real job failures
    behind a healthy-looking idle cycle, which is a worse defect than the one
    being fixed. So a dispatch failure must still propagate.
    """

    from app.services import async_worker_fleet

    class _LiveQueue:
        def dequeue(self, *, timeout_seconds: int) -> object:
            return type(
                "D",
                (),
                {
                    "delivery_id": "d1",
                    "job_id": "j1",
                    "attempt_id": "a1",
                    "job_type": "retrieval_indexing",
                    "target_id": "t1",
                    "caller_app": "c1",
                    "correlation_id": "corr",
                    "submitted_at": "2026-09-07T00:00:00Z",
                },
            )()

        def snapshot(self) -> object:
            return type("S", (), {"backend_available": True, "backend_id": "redis_queue"})()

    def _exploding_dispatch(**_: object) -> None:
        raise RuntimeError("job execution blew up")

    monkeypatch.setattr(async_worker_fleet, "get_async_delivery_queue", lambda: _LiveQueue())
    monkeypatch.setattr(
        async_worker_fleet,
        "get_async_runtime_posture",
        lambda: _real_posture(),
    )
    monkeypatch.setattr(async_worker_fleet, "_dispatch_delivery", _exploding_dispatch)
    monkeypatch.setattr(async_worker_fleet.settings, "async_worker_drain_enabled", False)

    with pytest.raises(RuntimeError, match="job execution blew up"):
        async_worker_fleet.process_next_async_delivery(worker_id=WORKER_ID, timeout_seconds=0)


@pytest.mark.parametrize(
    ("failures", "expected"),
    [
        (0, 0.25),
        (1, 0.5),
        (2, 1.0),
        (4, 4.0),
        (5, 5.0),
        (50, 5.0),
    ],
)
def test_queue_outage_backoff_is_bounded(failures: int, expected: float) -> None:
    """Surviving an outage must not mean hammering a dead backend forever.

    Without a cap the loop retries at the idle interval - several failed
    connections per second, each logging a traceback, for the whole outage.
    That is unbounded log growth introduced by the fix rather than by the
    defect. Without a BOUND on the cap, recovery would lag arbitrarily.
    """

    from app.services.async_worker_fleet import _idle_sleep_for_cycle

    assert (
        _idle_sleep_for_cycle(idle_sleep_seconds=0.25, consecutive_queue_failures=failures)
        == expected
    )


def test_the_backoff_cap_stays_inside_the_health_staleness_bound() -> None:
    """A recovering worker must refresh its marker before it can look stale.

    If the retry interval ever exceeded the staleness bound, a worker whose
    backend had returned would still be reported unhealthy purely because it
    was asleep - the original false-unhealthy defect, reintroduced by the
    backoff added to fix a different problem.
    """

    from app.services.async_worker_fleet import _QUEUE_BACKOFF_MAX_SECONDS

    assert _QUEUE_BACKOFF_MAX_SECONDS < settings.async_worker_liveness_max_age_seconds
