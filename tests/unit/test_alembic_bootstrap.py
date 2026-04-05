from app.config import settings
from app.operations import alembic_bootstrap


class _FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement) -> None:
        self.statements.append(str(statement))


class _FakeEngine:
    def __init__(self, *, dialect_name: str) -> None:
        self.dialect = type("Dialect", (), {"name": dialect_name})()
        self.connection = _FakeConnection()
        self.disposed = False

    def begin(self) -> _FakeConnection:
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


def test_ensure_alembic_version_table_capacity_widens_postgres_version_column(
    monkeypatch,
) -> None:
    settings.database_url = "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
    fake_engine = _FakeEngine(dialect_name="postgresql")
    monkeypatch.setattr(
        alembic_bootstrap,
        "create_engine",
        lambda database_url: fake_engine,
    )

    alembic_bootstrap.ensure_alembic_version_table_capacity()

    assert fake_engine.connection.statements == [
        "CREATE TABLE IF NOT EXISTS alembic_version (\n    version_num VARCHAR(128) NOT NULL\n)",
        "ALTER TABLE alembic_version\nALTER COLUMN version_num TYPE VARCHAR(128)",
    ]
    assert fake_engine.disposed is True


def test_ensure_alembic_version_table_capacity_skips_non_postgres_engines(
    monkeypatch,
) -> None:
    settings.database_url = "sqlite:///tmp/lotus-ai.db"
    fake_engine = _FakeEngine(dialect_name="sqlite")
    monkeypatch.setattr(
        alembic_bootstrap,
        "create_engine",
        lambda database_url: fake_engine,
    )

    alembic_bootstrap.ensure_alembic_version_table_capacity()

    assert fake_engine.connection.statements == []
    assert fake_engine.disposed is True
