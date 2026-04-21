from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


def extract_knowledge_query(*, payload: dict[str, Any], task_id: str) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{task_id} requires context.payload.query as a non-empty string.",
        )
    return query.strip()


def extract_knowledge_source_ids(*, payload: dict[str, Any], task_id: str) -> list[str]:
    raw_source_ids = payload.get("source_ids", [])
    if not isinstance(raw_source_ids, list) or any(
        not isinstance(source_id, str) or not source_id.strip() for source_id in raw_source_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{task_id} requires context.payload.source_ids to be a list of non-empty "
                "strings when supplied."
            ),
        )
    return [source_id.strip() for source_id in raw_source_ids]


def extract_knowledge_limit(*, payload: dict[str, Any], task_id: str) -> int:
    raw_limit = payload.get("limit", 5)
    if not isinstance(raw_limit, int) or isinstance(raw_limit, bool) or not 1 <= raw_limit <= 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{task_id} requires context.payload.limit to be an integer between 1 and 20 "
                "when supplied."
            ),
        )
    return raw_limit
