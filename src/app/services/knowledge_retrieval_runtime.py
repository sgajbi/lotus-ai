from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import RetrievalSearchRequest, RetrievalSearchResponse
from app.services.knowledge_retrieval_request import (
    extract_knowledge_limit,
    extract_knowledge_query,
    extract_knowledge_source_ids,
)
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
    query = extract_knowledge_query(payload=payload, task_id=context.capability.task_id)
    source_ids = extract_knowledge_source_ids(payload=payload, task_id=context.capability.task_id)
    limit = extract_knowledge_limit(payload=payload, task_id=context.capability.task_id)
    retrieval_response = search_sources(
        RetrievalSearchRequest(
            query=query,
            caller_app=context.request.caller.caller_app,
            correlation_id=context.request.caller.correlation_id,
            tenant_id=context.request.caller.tenant_id,
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
