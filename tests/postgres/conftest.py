"""PostgreSQL fence-proof lane (issue #344).

The CAS fences behind governed claims and hard-budget accounting are proven
concurrent on SQLite in the unit lane; this lane certifies the SAME guarded
statements on the production database engine. It is deliberately fail-closed
in CI: when ``LOTUS_AI_POSTGRES_TEST_REQUIRED`` is set, a missing or
unreachable database FAILS the lane rather than skipping it - a gate that
silently skips is a dead gate that looks like a pass. Locally, without the
required flag, the lane skips with an explicit reason unless
``LOTUS_AI_POSTGRES_TEST_URL`` points at a disposable PostgreSQL.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

_URL_VARIABLE = "LOTUS_AI_POSTGRES_TEST_URL"
_REQUIRED_VARIABLE = "LOTUS_AI_POSTGRES_TEST_REQUIRED"


def _postgres_url_or_none() -> str | None:
    url = os.environ.get(_URL_VARIABLE, "").strip()
    return url or None


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    url = _postgres_url_or_none()
    required = bool(os.environ.get(_REQUIRED_VARIABLE, "").strip())
    if url is None:
        if required:
            pytest.fail(
                f"{_REQUIRED_VARIABLE} is set but {_URL_VARIABLE} is not: the "
                "PostgreSQL fence lane must not silently skip in CI."
            )
        pytest.skip(
            f"set {_URL_VARIABLE} to a disposable PostgreSQL "
            "(e.g. postgresql+psycopg://lotus_ai:lotus_ai@localhost:5432/lotus_ai) "
            "to run the fence proofs locally"
        )
    if not url.startswith("postgresql"):
        pytest.fail(
            f"{_URL_VARIABLE} must point at PostgreSQL - this lane exists to "
            f"prove the fences on the production engine, got: {url!r}"
        )
    probe = create_engine(url, future=True, connect_args={"connect_timeout": 5})
    try:
        with probe.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        if required:
            pytest.fail(f"PostgreSQL at {_URL_VARIABLE} is unreachable in CI: {exc}")
        pytest.skip(f"PostgreSQL at {_URL_VARIABLE} is unreachable: {exc}")
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
    settings.database_url = url
    try:
        ensure_alembic_version_table_capacity()
        upgrade_database_to_head(url)
    finally:
        settings.database_url = previous_database_url
    return url
