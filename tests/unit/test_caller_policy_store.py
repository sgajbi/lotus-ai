from pathlib import Path

from app.config import settings
from app.repositories.memory_caller_policy_repository import InMemoryCallerPolicyRepository
from app.repositories.sqlalchemy_caller_policy_repository import SqlAlchemyCallerPolicyRepository
from app.services.caller_policy_store import (
    get_caller_policy_repository,
    reset_caller_policy_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_get_caller_policy_repository_returns_memory_repository_by_default() -> None:
    settings.access_control_store_mode = "memory"
    reset_caller_policy_store_cache()

    repository = get_caller_policy_repository()

    assert isinstance(repository, InMemoryCallerPolicyRepository)


def test_get_caller_policy_repository_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'caller-policy-store.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_caller_policy_store_cache()

    repository = get_caller_policy_repository()

    assert isinstance(repository, SqlAlchemyCallerPolicyRepository)


def test_get_caller_policy_repository_rejects_sqlalchemy_without_database_url() -> None:
    settings.access_control_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_caller_policy_store_cache()

    try:
        get_caller_policy_repository()
    except RuntimeError as exc:
        assert "LOTUS_AI_DATABASE_URL is required" in str(exc)
    else:
        raise AssertionError(
            "Expected RuntimeError when sqlalchemy access-control store has no database URL"
        )


def test_get_caller_policy_repository_rejects_unsupported_mode() -> None:
    settings.access_control_store_mode = "unsupported"
    reset_caller_policy_store_cache()

    try:
        get_caller_policy_repository()
    except RuntimeError as exc:
        assert "Unsupported LOTUS_AI_ACCESS_CONTROL_STORE_MODE" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for unsupported access-control store mode")
