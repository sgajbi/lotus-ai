from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory_artifact_repository import InMemoryArtifactRepository
from app.repositories.sqlalchemy_artifact_repository import SqlAlchemyArtifactRepository
from app.services.artifact_object_store import (
    FilesystemArtifactObjectStore,
    InMemoryArtifactObjectStore,
)
from app.services.artifact_store import (
    get_artifact_object_store,
    get_artifact_repository,
    reset_artifact_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_artifact_store_returns_cached_memory_instances_and_resets() -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    first_repo = get_artifact_repository()
    first_object_store = get_artifact_object_store()

    assert first_repo is get_artifact_repository()
    assert isinstance(first_repo, InMemoryArtifactRepository)
    assert first_object_store is get_artifact_object_store()
    assert isinstance(first_object_store, InMemoryArtifactObjectStore)

    reset_artifact_store_cache()

    assert get_artifact_repository() is not first_repo
    assert get_artifact_object_store() is not first_object_store


def test_artifact_store_builds_sqlalchemy_and_filesystem_backends(tmp_path: Path) -> None:
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "artifact-objects")
    settings.database_url = f"sqlite:///{tmp_path / 'artifact-store.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()

    repository = get_artifact_repository()
    object_store = get_artifact_object_store()

    assert isinstance(repository, SqlAlchemyArtifactRepository)
    assert isinstance(object_store, FilesystemArtifactObjectStore)


def test_artifact_store_rejects_invalid_configuration() -> None:
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.database_url = None
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL"):
        get_artifact_repository()

    settings.artifact_store_mode = "memory"
    with pytest.raises(RuntimeError, match="LOTUS_AI_ARTIFACT_OBJECT_STORE_ROOT"):
        get_artifact_object_store()

    settings.artifact_object_store_mode = "unsupported"
    with pytest.raises(RuntimeError, match="Unsupported artifact object-store mode"):
        get_artifact_object_store()

    settings.artifact_store_mode = "unsupported"
    with pytest.raises(RuntimeError, match="Unsupported artifact store mode"):
        get_artifact_repository()
