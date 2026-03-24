from __future__ import annotations

from copy import deepcopy

from app.repositories.artifact_repository import ArtifactRecord, ArtifactRepository


class InMemoryArtifactRepository(ArtifactRepository):
    def __init__(self) -> None:
        self._records: dict[str, ArtifactRecord] = {}

    def list_artifacts(self) -> list[ArtifactRecord]:
        return [
            deepcopy(self._records[artifact_id])
            for artifact_id in sorted(
                self._records, key=lambda item: self._records[item].created_at
            )
        ]

    def get_artifact(self, *, artifact_id: str) -> ArtifactRecord | None:
        record = self._records.get(artifact_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_artifact(self, record: ArtifactRecord) -> None:
        self._records[record.artifact_id] = deepcopy(record)
