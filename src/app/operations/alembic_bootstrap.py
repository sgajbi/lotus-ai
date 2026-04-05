from __future__ import annotations

from sqlalchemy import create_engine, text

from app.config import settings

_POSTGRES_ALTER_SQL = """
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(128) NOT NULL
);
ALTER TABLE alembic_version
ALTER COLUMN version_num TYPE VARCHAR(128);
"""


def ensure_alembic_version_table_capacity() -> None:
    if not settings.database_url:
        return

    engine = create_engine(settings.database_url)
    try:
        if engine.dialect.name != "postgresql":
            return
        with engine.begin() as connection:
            for statement in _POSTGRES_ALTER_SQL.strip().split(";"):
                normalized_statement = statement.strip()
                if normalized_statement:
                    connection.execute(text(normalized_statement))
    finally:
        engine.dispose()


if __name__ == "__main__":
    ensure_alembic_version_table_capacity()
