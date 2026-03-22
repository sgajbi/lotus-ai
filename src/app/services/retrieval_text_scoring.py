from __future__ import annotations

import re


def tokenize_retrieval_text(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token}


def lexical_overlap_ratio(*, query_terms: set[str], searchable_text: str) -> float:
    if not query_terms:
        return 0.0
    searchable_terms = tokenize_retrieval_text(searchable_text)
    if not searchable_terms:
        return 0.0
    return len(query_terms & searchable_terms) / len(query_terms)
