from __future__ import annotations

from app.contracts.retrieval import RetrievalSearchHit


def build_citation_entries(hits: list[RetrievalSearchHit]) -> list[dict[str, object]]:
    return [
        {
            "rank": index + 1,
            "source_id": hit.source_id,
            "score": hit.score,
            "snippet": hit.snippet,
        }
        for index, hit in enumerate(hits)
    ]


def top_support_score(hits: list[RetrievalSearchHit]) -> float:
    if not hits:
        return 0.0
    return max(hit.score for hit in hits)
