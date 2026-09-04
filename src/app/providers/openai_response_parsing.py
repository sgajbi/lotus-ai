"""OpenAI-compatible response parsing and structured-output shaping.

Split from the transport when the module budget fired (issue #314 S2b):
this family interprets provider RESPONSE payloads - JSON extraction,
structured-output construction, usage/typing coercions - and is consumed by
the transport and the live-provider tests. It carries no transport
mechanics: no retries, no billing, no telemetry.
"""

from __future__ import annotations

import json
from typing import Any


def as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def as_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def parse_json_object(value: str) -> dict[str, Any] | None:
    parsed, _ = parse_json_object_with_posture(value)
    return parsed


def parse_json_object_with_posture(value: str) -> tuple[dict[str, Any] | None, bool]:
    """Parse a model answer, reporting whether balanced-brace salvage ran.

    Salvage is a recovery, not a validation: the output validator downgrades
    or rejects salvaged output by runtime profile (issue #156).
    """

    normalized = strip_json_code_fence(value)
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        candidate = extract_balanced_json_object(normalized)
        if candidate is None:
            return None, True
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None, True
        return (parsed, True) if isinstance(parsed, dict) else (None, True)
    return (parsed if isinstance(parsed, dict) else None), False


def strip_json_code_fence(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("```json"):
        return normalized.removeprefix("```json").removesuffix("```").strip()
    if normalized.startswith("```"):
        return normalized.removeprefix("```").removesuffix("```").strip()
    return normalized


def extract_balanced_json_object(value: str) -> str | None:
    start = value.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(value[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]
    return None
