"""Docker HEALTHCHECK entrypoint for the dedicated async worker (issue #369).

Run as its own process by the container's HEALTHCHECK. It reads the liveness
marker the worker loop writes and exits 0 only when that marker is present,
recent, this worker's, and records a reachable queue backend.

Deliberately not an HTTP probe and deliberately not a server: the worker binds
no port, and standing one up purely to satisfy Docker would make the health
signal a statement about the probe rather than about the worker.

Exit codes are the contract Docker reads: 0 healthy, 1 unhealthy. The reason is
printed so `docker inspect` shows an operator WHY, not just that it failed.
"""

from __future__ import annotations

import json
import sys

from app.services.async_worker_health import evaluate_worker_health


def main() -> int:
    verdict = evaluate_worker_health()
    print(json.dumps(verdict.as_dict(), sort_keys=True))
    return 0 if verdict.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
