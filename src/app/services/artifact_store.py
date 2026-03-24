from __future__ import annotations

from app.config import settings
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.memory_artifact_repository import InMemoryArtifactRepository
from app.repositories.sqlalchemy_artifact_repository import SqlAlchemyArtifactRepository
from app.services.artifact_object_store import (
    ArtifactObjectStore,
    FilesystemArtifactObjectStore,
    InMemoryArtifactObjectStore,
)

_memory_artifact_repository = InMemoryArtifactRepository()
_sqlalchemy_artifact_repository: SqlAlchemyArtifactRepository | None = None
_memory_artifact_object_store = InMemoryArtifactObjectStore()
_filesystem_artifact_object_store: FilesystemArtifactObjectStore | None = None


def get_artifact_repository() -> ArtifactRepository:
    if settings.artifact_store_mode == "memory":
        return _memory_artifact_repository
    if settings.artifact_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_ARTIFACT_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_artifact_repository
        if _sqlalchemy_artifact_repository is None:
            _sqlalchemy_artifact_repository = SqlAlchemyArtifactRepository(settings.database_url)
        return _sqlalchemy_artifact_repository
    raise RuntimeError(f"Unsupported artifact store mode: {settings.artifact_store_mode}")


def get_artifact_object_store() -> ArtifactObjectStore:
    if settings.artifact_object_store_mode == "memory":
        return _memory_artifact_object_store
    if settings.artifact_object_store_mode == "filesystem":
        if not settings.artifact_object_store_root:
            raise RuntimeError(
                "LOTUS_AI_ARTIFACT_OBJECT_STORE_ROOT is required when "
                "LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE=filesystem."
            )
        global _filesystem_artifact_object_store
        if _filesystem_artifact_object_store is None:
            _filesystem_artifact_object_store = FilesystemArtifactObjectStore(
                settings.artifact_object_store_root
            )
        return _filesystem_artifact_object_store
    raise RuntimeError(
        f"Unsupported artifact object-store mode: {settings.artifact_object_store_mode}"
    )


def reset_artifact_store_cache() -> None:
    global _sqlalchemy_artifact_repository
    global _filesystem_artifact_object_store
    _sqlalchemy_artifact_repository = None
    _filesystem_artifact_object_store = None
