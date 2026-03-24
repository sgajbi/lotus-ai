from __future__ import annotations

from app.config import settings
from app.services.async_worker_fleet import run_dedicated_worker_loop


def main() -> None:
    run_dedicated_worker_loop(
        worker_id=settings.async_worker_id,
        timeout_seconds=settings.async_worker_queue_poll_seconds,
    )


if __name__ == "__main__":
    main()
