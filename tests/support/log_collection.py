"""Deterministic capture of the service's structured log lines.

Naive capture (pytest's ``caplog``) is unreliable here: the app logger tree
carries handlers, levels, propagation flags and a global ``logging.disable``
level that other tests and the app's own configuration mutate. This snapshots
that state, normalizes it for the duration of one test, and restores it - so a
test can assert on emitted lines regardless of the order it runs in.

Shared rather than copied: log attribution is asserted both by the logging
foundation tests and by the routing tests that check which candidate a line
names (issue #237).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from app.services.structured_logging import StructuredJsonFormatter

_NORMALIZED_CHILD_LOGGERS = ("app.http", "app.provider", "app.errors", "app.test")


class CollectingLogHandler(logging.Handler):
    """Collects formatted structured lines as parsed dicts."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[dict[str, object]] = []
        self.setFormatter(StructuredJsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))

    def events(self, event: str) -> list[dict[str, object]]:
        return [line for line in self.lines if line.get("event") == event]


@pytest.fixture
def app_log_collector() -> Iterator[CollectingLogHandler]:
    logger = logging.getLogger("app")
    snapshot = (list(logger.handlers), logger.level, logger.propagate)
    child_snapshots = {
        name: (child.level, child.propagate)
        for name in _NORMALIZED_CHILD_LOGGERS
        for child in (logging.getLogger(name),)
    }
    ambient_disable = logging.root.manager.disable

    handler = CollectingLogHandler()
    logging.disable(logging.NOTSET)
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    for name in child_snapshots:
        child = logging.getLogger(name)
        child.setLevel(logging.NOTSET)
        child.propagate = True
        child.disabled = False
    yield handler
    logger.handlers, level, propagate = snapshot[0], snapshot[1], snapshot[2]
    logger.setLevel(level)
    logger.propagate = propagate
    for name, (child_level, child_propagate) in child_snapshots.items():
        child = logging.getLogger(name)
        child.setLevel(child_level)
        child.propagate = child_propagate
    logging.disable(ambient_disable)
