from fastapi import HTTPException
from pytest import MonkeyPatch

from app.contracts.retrieval import (
    RetrievalIndexJobEventDescriptor,
    RetrievalIndexJobEventStatus,
    RetrievalIndexJobRefreshDescriptor,
    RetrievalIndexJobRefreshStatus,
    RetrievalPipelineStage,
)
from app.services.retrieval_indexing_refresh import refresh_retrieval_index_job


class _MissingRefreshRepository:
    def refresh_index_job(self, job_id: str) -> None:
        return None


class _DisappearingJobRepository:
    def __init__(self, refresh: RetrievalIndexJobRefreshDescriptor) -> None:
        self._refresh = refresh

    def refresh_index_job(self, job_id: str) -> RetrievalIndexJobRefreshDescriptor:
        return self._refresh

    def get_index_job(self, job_id: str) -> None:
        return None


def test_refresh_retrieval_index_job_raises_not_found_for_unknown_job(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.retrieval_indexing_refresh.get_retrieval_repository",
        lambda: _MissingRefreshRepository(),
    )

    try:
        refresh_retrieval_index_job("missing-job")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Unknown retrieval job_id: missing-job"
    else:
        raise AssertionError("Expected refresh lookup to raise HTTPException.")


def test_refresh_retrieval_index_job_raises_server_error_when_job_disappears(
    monkeypatch: MonkeyPatch,
) -> None:
    refresh = RetrievalIndexJobRefreshDescriptor(
        status=RetrievalIndexJobRefreshStatus.COMPLETED,
        refreshed_document_count=1,
        refreshed_chunk_count=1,
        persisted_embedding_count=0,
        replayed_embedding_count=1,
        message="refreshed",
        event=RetrievalIndexJobEventDescriptor(
            event_id="evt_1",
            job_id="retjob_lotus_platform_rfcs",
            stage=RetrievalPipelineStage.ENABLED,
            status=RetrievalIndexJobEventStatus.COMPLETED,
            recorded_at="2026-03-22T12:00:00Z",
            notes="refreshed",
        ),
    )
    monkeypatch.setattr(
        "app.services.retrieval_indexing_refresh.get_retrieval_repository",
        lambda: _DisappearingJobRepository(refresh),
    )

    try:
        refresh_retrieval_index_job("retjob_lotus_platform_rfcs")
    except HTTPException as exc:
        assert exc.status_code == 500
        assert exc.detail == (
            "Retrieval job disappeared during refresh: retjob_lotus_platform_rfcs"
        )
    else:
        raise AssertionError("Expected refresh lookup to raise HTTPException.")
