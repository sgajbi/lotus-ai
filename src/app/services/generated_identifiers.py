from __future__ import annotations

import hashlib

GENERATED_IDENTIFIER_MAX_LENGTH = 128
GENERATED_IDENTIFIER_DIGEST_LENGTH = 24


def bounded_generated_identifier(
    raw_identifier: str,
    *,
    readable_prefix: str,
    max_length: int = GENERATED_IDENTIFIER_MAX_LENGTH,
) -> str:
    """Keep deterministic generated ids inside the durable string contract.

    Short identifiers preserve their historical representation. Long values
    retain a purpose-specific prefix and bind the complete source identity in
    a collision-resistant digest.
    """

    if len(raw_identifier) <= max_length:
        return raw_identifier

    digest = hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()[
        :GENERATED_IDENTIFIER_DIGEST_LENGTH
    ]
    suffix = f"_{digest}"
    prefix_budget = max_length - len(suffix)
    return f"{readable_prefix[:prefix_budget]}{suffix}"
