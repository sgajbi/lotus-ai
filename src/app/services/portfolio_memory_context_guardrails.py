from __future__ import annotations

from typing import Any, Callable, cast

PORTFOLIO_MEMORY_EVENT_REF_LIMIT = 12

REQUIRED_CONTEXT_KEYS = frozenset(
    {
        "portfolio_id",
        "supportability_state",
        "context_content_hash",
        "support_boundary",
        "event_ref_limit",
        "event_ref_selection_policy",
        "event_refs_returned",
        "event_refs_omitted",
        "event_refs_truncated",
        "event_count",
        "source_systems",
        "reason_codes",
        "content_hash",
        "governance_policy",
        "event_refs",
    }
)

REQUIRED_GOVERNANCE_KEYS = frozenset(
    {
        "event_identity_scheme",
        "retention_policy",
        "redaction_policy",
        "audit_policy",
        "access_classification",
        "source_authority_policy",
    }
)

REQUIRED_EVENT_REF_KEYS = frozenset(
    {
        "event_identity",
        "event_type",
        "source_system",
        "source_type",
        "source_id",
        "event_time",
        "event_ref_selection_rank",
        "retention_policy",
        "redaction_policy",
        "audit_policy",
        "access_classification",
    }
)

NO_RAW_PAYLOADS_POLICY = "NO_RAW_PAYLOADS"


def validate_optional_portfolio_memory_context(
    *,
    payload: dict[str, object],
    evidence_portfolio_id: object,
    forbidden_field_names: frozenset[str],
    reject: Callable[[str], None],
) -> dict[str, Any] | None:
    context = payload.get("portfolio_memory_context")
    if context is None:
        return None
    if not isinstance(context, dict):
        reject("Portfolio memory context must be an object when supplied.")
    context = cast(dict[str, Any], context)

    missing = sorted(REQUIRED_CONTEXT_KEYS.difference(context.keys()))
    if missing:
        reject("Missing portfolio_memory_context fields: " + ", ".join(missing))

    forbidden_fields = sorted(_find_forbidden_field_names(context, forbidden_field_names))
    if forbidden_fields:
        reject("Forbidden portfolio memory fields present: " + ", ".join(forbidden_fields))

    if context.get("portfolio_id") != evidence_portfolio_id:
        reject("Portfolio memory context portfolio_id must match AI evidence portfolio_id.")
    if not isinstance(context.get("content_hash"), str) or not context["content_hash"]:
        reject("Portfolio memory context requires a source content_hash.")
    if (
        not isinstance(context.get("context_content_hash"), str)
        or not context["context_content_hash"]
    ):
        reject("Portfolio memory context requires a context_content_hash.")
    if not isinstance(context.get("support_boundary"), str) or not context["support_boundary"]:
        reject("Portfolio memory context requires a support_boundary.")
    if not isinstance(context.get("event_count"), int) or context["event_count"] < 0:
        reject("Portfolio memory context event_count must be a non-negative integer.")
    if (
        not isinstance(context.get("event_ref_limit"), int)
        or context["event_ref_limit"] < 0
        or context["event_ref_limit"] > PORTFOLIO_MEMORY_EVENT_REF_LIMIT
    ):
        reject("Portfolio memory context event_ref_limit must be within the bounded limit.")
    if (
        not isinstance(context.get("event_ref_selection_policy"), str)
        or not context["event_ref_selection_policy"]
    ):
        reject("Portfolio memory context requires an event_ref_selection_policy.")

    _require_string_list(context, "source_systems", reject)
    _require_string_list(context, "reason_codes", reject)
    governance_policy = _require_mapping(context, "governance_policy", reject)
    missing_governance = sorted(REQUIRED_GOVERNANCE_KEYS.difference(governance_policy.keys()))
    if missing_governance:
        reject(
            "Missing portfolio_memory_context governance_policy fields: "
            + ", ".join(missing_governance)
        )
    if governance_policy.get("redaction_policy") != NO_RAW_PAYLOADS_POLICY:
        reject("Portfolio memory context must enforce NO_RAW_PAYLOADS redaction policy.")
    source_authority = governance_policy.get("source_authority_policy")
    if not isinstance(source_authority, str) or "must not reconstruct" not in source_authority:
        reject("Portfolio memory context must carry source-authority no-reconstruction policy.")

    event_refs = context.get("event_refs")
    if not isinstance(event_refs, list):
        reject("Portfolio memory context event_refs must be a list.")
    event_refs = cast(list[Any], event_refs)
    if len(event_refs) > PORTFOLIO_MEMORY_EVENT_REF_LIMIT:
        reject(
            "Portfolio memory context event_refs exceeds bounded limit "
            f"{PORTFOLIO_MEMORY_EVENT_REF_LIMIT}."
        )
    ranks: list[int] = []
    for index, event_ref in enumerate(event_refs):
        if not isinstance(event_ref, dict):
            reject(f"Portfolio memory context event_refs[{index}] must be an object.")
        event_ref = cast(dict[str, Any], event_ref)
        missing_event_fields = sorted(REQUIRED_EVENT_REF_KEYS.difference(event_ref.keys()))
        if missing_event_fields:
            reject(
                f"Missing portfolio_memory_context event_refs[{index}] fields: "
                + ", ".join(missing_event_fields)
            )
        if event_ref.get("redaction_policy") != NO_RAW_PAYLOADS_POLICY:
            reject(
                f"Portfolio memory context event_refs[{index}] must enforce "
                "NO_RAW_PAYLOADS redaction policy."
            )
        rank = event_ref.get("event_ref_selection_rank")
        if not isinstance(rank, int):
            reject(
                f"Portfolio memory context event_refs[{index}] must include integer "
                "event_ref_selection_rank."
            )
            continue
        ranks.append(rank)
        if not isinstance(event_ref.get("event_time"), str) or not event_ref["event_time"]:
            reject(f"Portfolio memory context event_refs[{index}] must include event_time.")
    if ranks != list(range(1, len(event_refs) + 1)):
        reject("Portfolio memory context event_ref_selection_rank must be contiguous from 1.")
    returned = context.get("event_refs_returned")
    omitted = context.get("event_refs_omitted")
    truncated = context.get("event_refs_truncated")
    if returned != len(event_refs):
        reject("Portfolio memory context event_refs_returned must match event_refs length.")
    expected_omitted = max(0, context["event_count"] - len(event_refs))
    if omitted != expected_omitted:
        reject("Portfolio memory context event_refs_omitted must match omitted event count.")
    if truncated is not (expected_omitted > 0):
        reject("Portfolio memory context event_refs_truncated must match omitted event posture.")

    return context


def portfolio_memory_context_summary(context_payload: dict[str, object]) -> dict[str, object]:
    context = context_payload.get("portfolio_memory_context")
    if not isinstance(context, dict):
        return {
            "portfolio_memory_status": "not_supplied",
            "portfolio_memory_content_hash": "",
            "portfolio_memory_context_content_hash": "",
            "portfolio_memory_event_count": 0,
            "portfolio_memory_event_ref_count": 0,
            "portfolio_memory_event_refs_omitted": 0,
            "portfolio_memory_event_refs_truncated": False,
            "portfolio_memory_source_systems": [],
            "portfolio_memory_event_types": [],
            "portfolio_memory_supportability_state": "",
        }

    event_refs = context.get("event_refs")
    source_systems = context.get("source_systems")
    return {
        "portfolio_memory_status": "supplied",
        "portfolio_memory_content_hash": context.get("content_hash", ""),
        "portfolio_memory_context_content_hash": context.get("context_content_hash", ""),
        "portfolio_memory_event_count": context.get("event_count", 0),
        "portfolio_memory_event_ref_count": len(event_refs) if isinstance(event_refs, list) else 0,
        "portfolio_memory_event_refs_omitted": context.get("event_refs_omitted", 0),
        "portfolio_memory_event_refs_truncated": context.get("event_refs_truncated", False),
        "portfolio_memory_source_systems": (
            sorted(item for item in source_systems if isinstance(item, str))
            if isinstance(source_systems, list)
            else []
        ),
        "portfolio_memory_event_types": _event_types(event_refs),
        "portfolio_memory_supportability_state": context.get("supportability_state", ""),
    }


def _require_mapping(
    payload: dict[str, Any],
    key: str,
    reject: Callable[[str], None],
) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        reject(f"Portfolio memory context requires object field `{key}`.")
    return cast(dict[str, Any], value)


def _require_string_list(
    payload: dict[str, Any],
    key: str,
    reject: Callable[[str], None],
) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        reject(f"Portfolio memory context requires string-list field `{key}`.")
    return cast(list[str], value)


def _find_forbidden_field_names(value: Any, forbidden_field_names: frozenset[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower()
            if normalized in forbidden_field_names:
                found.add(normalized)
            found.update(_find_forbidden_field_names(item, forbidden_field_names))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_field_names(item, forbidden_field_names))
    return found


def _event_types(event_refs: object) -> list[str]:
    if not isinstance(event_refs, list):
        return []
    event_types: set[str] = set()
    for event_ref in event_refs:
        if not isinstance(event_ref, dict):
            continue
        event_type = event_ref.get("event_type")
        if isinstance(event_type, str):
            event_types.add(event_type)
    return sorted(event_types)
