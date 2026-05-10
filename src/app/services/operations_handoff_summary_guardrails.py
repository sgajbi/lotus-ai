from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, status

from app.services.portfolio_memory_context_guardrails import (
    validate_optional_portfolio_memory_context,
)
from app.services.wave_pm_memo_guardrails import (
    FORBIDDEN_FIELD_NAMES,
    REQUIRED_FORBIDDEN_ACTIONS,
    REQUIRED_WAVE_REPORT_INPUT_KEYS,
)

FORBIDDEN_REQUESTED_OUTPUTS = frozenset(
    {
        "approval_decision",
        "client_message",
        "execution_instruction",
        "order_ticket",
        "place_orders",
        "recommend_trade",
        "rebalance_approval",
        "routing_instruction",
    }
)

ALLOWED_REQUESTED_OUTPUTS = frozenset(
    {
        "operations_summary",
        "execution_prerequisites",
        "blocking_conditions",
        "support_references",
        "evidence_gaps",
    }
)


def validate_operations_handoff_summary_payload(payload: dict[str, object]) -> None:
    if "memo_request" in payload:
        _reject(
            "Operations handoff summary payload must not include wave memo `memo_request`; "
            "use `handoff_summary_request` only."
        )
    wave_report_input = _require_object_section(payload, "wave_report_input")
    summary_request = _require_object_section(payload, "handoff_summary_request")
    supportability = _require_object_section(payload, "supportability")

    missing = sorted(REQUIRED_WAVE_REPORT_INPUT_KEYS.difference(wave_report_input.keys()))
    if missing:
        _reject("Missing DpmWaveReportInput fields: " + ", ".join(missing))

    forbidden_fields = sorted(_find_forbidden_field_names(wave_report_input))
    if forbidden_fields:
        _reject("Forbidden wave report input fields present: " + ", ".join(forbidden_fields))

    forbidden_actions = set(_require_string_list(supportability, "forbidden_actions"))
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject("Missing required forbidden-action guardrails: " + ", ".join(missing_actions))

    requested_outputs = set(_require_string_list(summary_request, "requested_outputs"))
    forbidden_outputs = sorted(FORBIDDEN_REQUESTED_OUTPUTS.intersection(requested_outputs))
    if forbidden_outputs:
        _reject("Forbidden operations handoff outputs requested: " + ", ".join(forbidden_outputs))
    unsupported_outputs = sorted(requested_outputs.difference(ALLOWED_REQUESTED_OUTPUTS))
    if unsupported_outputs:
        _reject(
            "Unsupported operations handoff outputs requested: " + ", ".join(unsupported_outputs)
        )

    if bool(wave_report_input.get("external_execution_claimed")):
        _reject("Operations handoff summary cannot claim external execution authority.")
    if wave_report_input.get("redaction_policy") != "NO_RAW_PAYLOADS":
        _reject("DpmWaveReportInput must use NO_RAW_PAYLOADS redaction policy.")

    items = wave_report_input.get("items")
    if not isinstance(items, list) or not items:
        _reject("Operations handoff summary requires at least one bounded wave item.")
    bounded_items = cast(list[object], items)
    if not _has_staged_or_ready_item(bounded_items):
        _reject("Operations handoff summary requires staged or handoff-ready wave item evidence.")

    handoff_refs = wave_report_input.get("handoff_refs")
    if not isinstance(handoff_refs, list) or not handoff_refs:
        _reject("Operations handoff summary requires non-empty handoff_refs.")
    bounded_handoff_refs = cast(list[object], handoff_refs)
    if not all(_is_bounded_handoff_ref(ref) for ref in bounded_handoff_refs):
        _reject(
            "Operations handoff refs must carry ref_type, ref_id, source_system, and content_hash."
        )

    source_refs = wave_report_input.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        _reject("DpmWaveReportInput source_refs must be a non-empty list.")

    validate_optional_portfolio_memory_context(
        payload=payload,
        evidence_portfolio_id=_single_portfolio_id(bounded_items),
        forbidden_field_names=FORBIDDEN_FIELD_NAMES,
        reject=_reject,
    )


def _has_staged_or_ready_item(items: list[object]) -> bool:
    eligible_states = {"STAGED", "HANDOFF_READY", "READY", "READY_FOR_HANDOFF"}
    return any(
        isinstance(item, dict)
        and isinstance(item.get("state"), str)
        and item["state"] in eligible_states
        for item in items
    )


def _is_bounded_handoff_ref(ref: object) -> bool:
    if not isinstance(ref, dict):
        return False
    return all(isinstance(ref.get(key), str) and ref[key] for key in _HANDOFF_REF_KEYS)


_HANDOFF_REF_KEYS = ("ref_type", "ref_id", "source_system", "content_hash")


def _single_portfolio_id(items: object) -> str | None:
    if not isinstance(items, list):
        return None
    portfolio_ids = {
        item.get("portfolio_id")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("portfolio_id"), str)
    }
    if len(portfolio_ids) == 1:
        return next(iter(portfolio_ids))
    return None


def _require_object_section(payload: dict[str, object], key: str) -> dict[str, Any]:
    section = payload.get(key)
    if not isinstance(section, dict):
        _reject(f"Operations handoff summary payload requires object section `{key}`.")
    return cast(dict[str, Any], section)


def _require_string_list(section: dict[str, Any], key: str) -> list[str]:
    value = section.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _reject(f"Operations handoff summary payload requires string-list field `{key}`.")
    return cast(list[str], value)


def _find_forbidden_field_names(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower()
            if normalized in FORBIDDEN_FIELD_NAMES:
                found.add(normalized)
            found.update(_find_forbidden_field_names(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_field_names(item))
    return found


def _reject(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"OPERATIONS_HANDOFF_SUMMARY_GUARDRAIL_BLOCKED: {detail}",
    )
