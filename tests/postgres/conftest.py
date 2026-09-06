"""PostgreSQL fence-proof lane (issue #344).

The CAS fences behind governed claims and hard-budget accounting are proven
concurrent on SQLite in the unit lane; this lane certifies the SAME guarded
statements on the production database engine. It is deliberately fail-closed
in CI: when ``LOTUS_AI_POSTGRES_TEST_REQUIRED`` is set, a missing or
unreachable database FAILS the lane rather than skipping it - a gate that
silently skips is a dead gate that looks like a pass. Locally, without the
required flag, the lane skips with an explicit reason unless
``LOTUS_AI_POSTGRES_TEST_URL`` points at a disposable PostgreSQL.

The posture decisions live in ``tests/support/postgres_lane.py`` so they are
provable without a database; see ``tests/unit/test_postgres_lane_gating.py``.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from tests.support.postgres_lane import (
    REQUIRED_VARIABLE,
    URL_VARIABLE,
    decide_lane_start,
    decide_unreachable,
)


def _resolve(decision_action: str, reason: str) -> None:
    if decision_action == "fail":
        pytest.fail(reason)
    if decision_action == "skip":
        pytest.skip(reason)


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    url = os.environ.get(URL_VARIABLE)
    required = bool(os.environ.get(REQUIRED_VARIABLE, "").strip())

    start = decide_lane_start(url=url, required=required)
    _resolve(start.action, start.reason)
    resolved_url = (url or "").strip()

    probe = create_engine(resolved_url, future=True, connect_args={"connect_timeout": 5})
    try:
        with probe.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        unreachable = decide_unreachable(required=required, error=str(exc))
        _resolve(unreachable.action, unreachable.reason)
    finally:
        probe.dispose()

    # Applying the real migration chain is itself part of the proof: the
    # schema the fences run against on PG is the one operators deploy, in
    # the deployed boot order - scripts/docker/start-api.sh widens the
    # alembic_version column BEFORE upgrading, because several revision ids
    # exceed alembic's default VARCHAR(32) (only PostgreSQL enforces it).
    from app.config import settings
    from app.operations.alembic_bootstrap import ensure_alembic_version_table_capacity
    from tests.support.migration_runner import upgrade_database_to_head

    previous_database_url = settings.database_url
    settings.database_url = resolved_url
    try:
        ensure_alembic_version_table_capacity()
        upgrade_database_to_head(resolved_url)
    finally:
        settings.database_url = previous_database_url
    return resolved_url
