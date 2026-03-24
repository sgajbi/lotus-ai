from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredArtifactObject:
    object_key: str
    content_type: str
    payload: bytes

    @property
    def byte_size(self) -> int:
        return len(self.payload)

    @property
    def checksum_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


class ArtifactObjectStore(Protocol):
    def put_object(
        self, *, object_key: str, payload: bytes, content_type: str
    ) -> StoredArtifactObject:
        """Persist one payload object and return the stored descriptor."""

    def get_object(self, *, object_key: str) -> StoredArtifactObject | None:
        """Read one payload object if it exists."""

    def delete_object(self, *, object_key: str) -> None:
        """Delete one payload object if present."""


class InMemoryArtifactObjectStore(ArtifactObjectStore):
    def __init__(self) -> None:
        self._objects: dict[str, StoredArtifactObject] = {}

    def put_object(
        self, *, object_key: str, payload: bytes, content_type: str
    ) -> StoredArtifactObject:
        stored = StoredArtifactObject(
            object_key=object_key,
            content_type=content_type,
            payload=bytes(payload),
        )
        self._objects[object_key] = stored
        return stored

    def get_object(self, *, object_key: str) -> StoredArtifactObject | None:
        stored = self._objects.get(object_key)
        if stored is None:
            return None
        return StoredArtifactObject(
            object_key=stored.object_key,
            content_type=stored.content_type,
            payload=bytes(stored.payload),
        )

    def delete_object(self, *, object_key: str) -> None:
        self._objects.pop(object_key, None)


class FilesystemArtifactObjectStore(ArtifactObjectStore):
    def __init__(self, root_path: str) -> None:
        self._root_path = Path(root_path)
        self._root_path.mkdir(parents=True, exist_ok=True)

    def put_object(
        self, *, object_key: str, payload: bytes, content_type: str
    ) -> StoredArtifactObject:
        payload_path, metadata_path = self._resolve_paths(object_key)
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.write_bytes(payload)
        metadata_path.write_text(
            json.dumps({"content_type": content_type}, indent=2),
            encoding="utf-8",
        )
        return StoredArtifactObject(
            object_key=object_key,
            content_type=content_type,
            payload=bytes(payload),
        )

    def get_object(self, *, object_key: str) -> StoredArtifactObject | None:
        payload_path, metadata_path = self._resolve_paths(object_key)
        if not payload_path.exists() or not metadata_path.exists():
            return None
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return StoredArtifactObject(
            object_key=object_key,
            content_type=str(metadata["content_type"]),
            payload=payload_path.read_bytes(),
        )

    def delete_object(self, *, object_key: str) -> None:
        payload_path, metadata_path = self._resolve_paths(object_key)
        if payload_path.exists():
            payload_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()

    def _resolve_paths(self, object_key: str) -> tuple[Path, Path]:
        normalized = object_key.replace("\\", "/").strip("/")
        payload_path = self._root_path / normalized
        metadata_path = payload_path.with_suffix(payload_path.suffix + ".meta.json")
        return payload_path, metadata_path
