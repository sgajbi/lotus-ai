from __future__ import annotations

import re


def tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token}


def score_terms(*, query: str, searchable_text: str) -> float:
    query_terms = tokenize(query)
    if not query_terms:
        return 0.0
    searchable_terms = tokenize(searchable_text)
    overlap_count = len(query_terms & searchable_terms)
    if overlap_count == 0:
        return 0.0
    return overlap_count / len(query_terms)
