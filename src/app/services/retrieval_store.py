from __future__ import annotations

from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.repositories.retrieval_repository import RetrievalRepository

_retrieval_repository: RetrievalRepository | None = None


def get_retrieval_repository() -> RetrievalRepository:
    global _retrieval_repository
    if _retrieval_repository is None:
        _retrieval_repository = InMemoryRetrievalRepository()
    return _retrieval_repository


def reset_retrieval_repository() -> None:
    global _retrieval_repository
    _retrieval_repository = None
