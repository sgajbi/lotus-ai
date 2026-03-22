from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.retrieval import RetrievalIndexJobRefreshResponse
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository


def refresh_retrieval_index_job(job_id: str) -> RetrievalIndexJobRefreshResponse:
    repository = get_retrieval_repository()
    refresh = repository.refresh_index_job(job_id)
    if refresh is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown retrieval job_id: {job_id}",
        )

    job = repository.get_index_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval job disappeared during refresh: {job_id}",
        )

    return RetrievalIndexJobRefreshResponse(
        service=settings.service_name,
        vector_store=VECTOR_STORE_STRATEGY,
        job=job,
        refresh=refresh,
    )
