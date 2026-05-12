from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, status

from app.services.portfolio_memory_context_guardrails import (
    validate_optional_portfolio_memory_context,
)
from app.services.wave_pm_memo_guardrails import FORBIDDEN_FIELD_NAMES

REQUIRED_EXCEPTION_SUMMARY_INPUT_KEYS = frozenset(
    {
        "contract_version",
        "portfolio_id",
        "mandate_id",
        "as_of_date",
        "generated_at",
        "exception_count",
        "exceptions",
        "source_refs",
        "redaction_policy",
        "evidence_ref",
        "content_hash",
    }
)

REQUIRED_FORBIDDEN_ACTIONS = frozenset(
    {
        "approve_rebalance",
        "contact_client",
        "invent_missing_evidence",
        "override_controls",
        "place_orders",
        "score_portfolio_manager",
    }
)

FORBIDDEN_REQUESTED_OUTPUTS = frozenset(
    {
        "approval_decision",
        "client_message",
        "execution_instruction",
        "order_ticket",
        "place_orders",
        "portfolio_manager_score",
        "recommend_trade",
        "rebalance_approval",
        "routing_instruction",
    }
)

ALLOWED_REQUESTED_OUTPUTS = frozenset(
    {
        "exception_summary",
        "severity_summary",
        "recommended_triage",
        "support_references",
        "evidence_gaps",
    }
)


def validate_dpm_exception_summary_payload(payload: dict[str, object]) -> None:
    exception_input = _require_object_section(payload, "exception_summary_input")
    summary_request = _require_object_section(payload, "exception_summary_request")
    supportability = _require_object_section(payload, "supportability")

    missing = sorted(REQUIRED_EXCEPTION_SUMMARY_INPUT_KEYS.difference(exception_input.keys()))
    if missing:
        _reject("Missing exception summary input fields: " + ", ".join(missing))

    forbidden_fields = sorted(_find_forbidden_field_names(exception_input))
    if forbidden_fields:
        _reject("Forbidden exception summary input fields present: " + ", ".join(forbidden_fields))

    if exception_input.get("redaction_policy") != "NO_RAW_PAYLOADS":
        _reject("Exception summary input must use NO_RAW_PAYLOADS redaction policy.")

    exceptions = exception_input.get("exceptions")
    if not isinstance(exceptions, list) or not exceptions:
        _reject("Exception summary requires at least one bounded monitoring exception.")
    bounded_exceptions = cast(list[object], exceptions)
    if not all(_is_bounded_exception(item) for item in bounded_exceptions):
        _reject(
            "Each exception must carry exception_id, portfolio_id, severity, state, "
            "reason_code, recommended_action, and source_refs."
        )

    declared_count = exception_input.get("exception_count")
    if not isinstance(declared_count, int) or declared_count != len(bounded_exceptions):
        _reject("exception_count must equal the number of supplied bounded exceptions.")

    source_refs = exception_input.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        _reject("Exception summary input source_refs must be a non-empty list.")
    bounded_source_refs = cast(list[object], source_refs)
    if not all(
        isinstance(ref, dict) and _has_required_ref_fields(ref) for ref in bounded_source_refs
    ):
        _reject("Exception summary input source_refs must be bounded and source-linked.")

    evidence_ref = exception_input.get("evidence_ref")
    if not isinstance(evidence_ref, dict) or not _has_required_ref_fields(evidence_ref):
        _reject("Exception summary input evidence_ref must be bounded and source-linked.")

    portfolio_id = exception_input.get("portfolio_id")
    exception_portfolio_id = _single_portfolio_id(bounded_exceptions)
    if not isinstance(portfolio_id, str) or portfolio_id != exception_portfolio_id:
        _reject("Exception summary portfolio_id must match all supplied exceptions.")

    requested_outputs = set(_require_string_list(summary_request, "requested_outputs"))
    forbidden_outputs = sorted(FORBIDDEN_REQUESTED_OUTPUTS.intersection(requested_outputs))
    if forbidden_outputs:
        _reject("Forbidden exception summary outputs requested: " + ", ".join(forbidden_outputs))
    unsupported_outputs = sorted(requested_outputs.difference(ALLOWED_REQUESTED_OUTPUTS))
    if unsupported_outputs:
        _reject(
            "Unsupported exception summary outputs requested: " + ", ".join(unsupported_outputs)
        )

    forbidden_actions = set(_require_string_list(supportability, "forbidden_actions"))
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject("Missing required forbidden-action guardrails: " + ", ".join(missing_actions))

    validate_optional_portfolio_memory_context(
        payload=payload,
        evidence_portfolio_id=exception_portfolio_id,
        forbidden_field_names=FORBIDDEN_FIELD_NAMES,
        reject=_reject,
    )


def _is_bounded_exception(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    required_string_keys = (
        "exception_id",
        "portfolio_id",
        "severity",
        "state",
        "reason_code",
        "recommended_action",
    )
    if not all(isinstance(item.get(key), str) and item[key] for key in required_string_keys):
        return False
    source_refs = item.get("source_refs")
    return (
        isinstance(source_refs, list)
        and bool(source_refs)
        and all(isinstance(ref, dict) and _has_required_ref_fields(ref) for ref in source_refs)
    )


def _has_required_ref_fields(ref: dict[str, object]) -> bool:
    return all(
        isinstance(ref.get(key), str) and ref[key]
        for key in ("source_system", "source_type", "source_id", "content_hash")
    )


def _single_portfolio_id(items: list[object]) -> str | None:
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
        _reject(f"Exception summary payload requires object section `{key}`.")
    return cast(dict[str, Any], section)


def _require_string_list(section: dict[str, Any], key: str) -> list[str]:
    value = section.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _reject(f"Exception summary payload requires string-list field `{key}`.")
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
        detail=f"DPM_EXCEPTION_SUMMARY_GUARDRAIL_BLOCKED: {detail}",
    )
