from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from app.contracts.retrieval import RetrievalSearchRequest, RetrievalSearchResponse
from app.services.retrieval_service import search_sources
from app.services.task_execution_models import TaskExecutionContext


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    query: str
    source_ids: list[str]
    limit: int
    retrieval_response: RetrievalSearchResponse


def execute_knowledge_retrieval(*, context: TaskExecutionContext) -> KnowledgeRetrievalResult:
    payload = context.request.context.payload
    query = _extract_query(payload=payload, task_id=context.capability.task_id)
    source_ids = _extract_source_ids(payload=payload, task_id=context.capability.task_id)
    limit = _extract_limit(payload=payload, task_id=context.capability.task_id)
    retrieval_response = search_sources(
        RetrievalSearchRequest(
            query=query,
            caller_app=context.request.caller.caller_app,
            correlation_id=context.request.caller.correlation_id,
            source_ids=source_ids,
            limit=limit,
        )
    )
    return KnowledgeRetrievalResult(
        query=query,
        source_ids=source_ids,
        limit=limit,
        retrieval_response=retrieval_response,
    )


def _extract_query(*, payload: dict[str, Any], task_id: str) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{task_id} requires context.payload.query as a non-empty string.",
        )
    return query.strip()


def _extract_source_ids(*, payload: dict[str, Any], task_id: str) -> list[str]:
    raw_source_ids = payload.get("source_ids", [])
    if not isinstance(raw_source_ids, list) or any(
        not isinstance(source_id, str) or not source_id.strip() for source_id in raw_source_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{task_id} requires context.payload.source_ids to be a list of non-empty "
                "strings when supplied."
            ),
        )
    return [source_id.strip() for source_id in raw_source_ids]


def _extract_limit(*, payload: dict[str, Any], task_id: str) -> int:
    raw_limit = payload.get("limit", 5)
    if not isinstance(raw_limit, int) or isinstance(raw_limit, bool) or not 1 <= raw_limit <= 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{task_id} requires context.payload.limit to be an integer between 1 and 20 "
                "when supplied."
            ),
        )
    return raw_limit
