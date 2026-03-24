from pathlib import Path

from app.services.artifact_object_store import (
    FilesystemArtifactObjectStore,
    InMemoryArtifactObjectStore,
)


def test_in_memory_artifact_object_store_round_trips_payload() -> None:
    store = InMemoryArtifactObjectStore()

    stored = store.put_object(
        object_key="evaluation/run-1/case-bundle.json",
        payload=b'{"ok":true}',
        content_type="application/json",
    )

    loaded = store.get_object(object_key="evaluation/run-1/case-bundle.json")

    assert loaded is not None
    assert loaded.payload == b'{"ok":true}'
    assert loaded.content_type == "application/json"
    assert loaded.byte_size == stored.byte_size
    assert loaded.checksum_sha256 == stored.checksum_sha256


def test_filesystem_artifact_object_store_round_trips_payload(tmp_path: Path) -> None:
    store = FilesystemArtifactObjectStore(str(tmp_path / "artifacts"))

    stored = store.put_object(
        object_key="async/job-9/output.json",
        payload=b'{"status":"done"}',
        content_type="application/json",
    )

    loaded = store.get_object(object_key="async/job-9/output.json")

    assert loaded is not None
    assert loaded.payload == b'{"status":"done"}'
    assert loaded.content_type == "application/json"
    assert loaded.checksum_sha256 == stored.checksum_sha256
