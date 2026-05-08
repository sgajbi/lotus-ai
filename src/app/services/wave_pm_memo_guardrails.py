from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, status

from app.services.portfolio_memory_context_guardrails import (
    validate_optional_portfolio_memory_context,
)

REQUIRED_WAVE_REPORT_INPUT_KEYS = frozenset(
    {
        "contract_version",
        "wave_id",
        "wave_content_hash",
        "wave_state",
        "trigger_type",
        "trigger_id",
        "trigger_rationale",
        "as_of_date",
        "generated_at",
        "aggregate_metrics",
        "supportability",
        "proof_pack_posture",
        "items",
        "events",
        "handoff_refs",
        "source_refs",
        "redaction_policy",
        "external_execution_claimed",
        "evidence_ref",
        "content_hash",
    }
)

REQUIRED_FORBIDDEN_ACTIONS = frozenset(
    {
        "place_orders",
        "approve_rebalance",
        "override_controls",
        "invent_missing_evidence",
        "contact_client",
    }
)

FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "account_number",
        "client_name",
        "client_id",
        "email",
        "phone",
        "raw_payload",
        "raw_request",
        "raw_response",
        "secret",
        "ssn",
        "token",
    }
)

FORBIDDEN_REQUESTED_OUTPUTS = frozenset(
    {
        "approval_decision",
        "client_message",
        "execution_instruction",
        "order_ticket",
        "pm_score",
        "recommend_trade",
        "rebalance_approval",
    }
)

ALLOWED_REQUESTED_OUTPUTS = frozenset(
    {
        "wave_pm_memo",
        "wave_rationale_summary",
        "approval_checklist",
        "risk_caveats",
        "operations_handoff",
        "evidence_gaps",
    }
)


def validate_wave_pm_memo_payload(payload: dict[str, object]) -> None:
    wave_report_input = _require_object_section(payload, "wave_report_input")
    memo_request = _require_object_section(payload, "memo_request")
    supportability = _require_object_section(payload, "supportability")

    missing = sorted(REQUIRED_WAVE_REPORT_INPUT_KEYS.difference(wave_report_input.keys()))
    if missing:
        _reject("Missing DpmWaveReportInput fields: " + ", ".join(missing))

    forbidden_fields = sorted(_find_forbidden_field_names(wave_report_input))
    if forbidden_fields:
        _reject("Forbidden wave report input fields present: " + ", ".join(forbidden_fields))

    forbidden_actions = _require_string_list(supportability, "forbidden_actions")
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject("Missing required forbidden-action guardrails: " + ", ".join(missing_actions))

    requested_outputs = set(_require_string_list(memo_request, "requested_outputs"))
    forbidden_outputs = sorted(FORBIDDEN_REQUESTED_OUTPUTS.intersection(requested_outputs))
    if forbidden_outputs:
        _reject("Forbidden wave memo outputs requested: " + ", ".join(forbidden_outputs))
    unsupported_outputs = sorted(requested_outputs.difference(ALLOWED_REQUESTED_OUTPUTS))
    if unsupported_outputs:
        _reject("Unsupported wave memo outputs requested: " + ", ".join(unsupported_outputs))

    items = wave_report_input.get("items")
    if not isinstance(items, list) or not items:
        _reject("DpmWaveReportInput requires at least one bounded wave item.")
    source_refs = wave_report_input.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        _reject("DpmWaveReportInput source_refs must be a non-empty list.")
    proof_pack_posture = wave_report_input.get("proof_pack_posture")
    if not isinstance(proof_pack_posture, dict):
        _reject("DpmWaveReportInput proof_pack_posture must be an object.")

    if bool(wave_report_input.get("external_execution_claimed")):
        _reject("Wave memo generation cannot claim external execution authority.")
    if wave_report_input.get("redaction_policy") != "NO_RAW_PAYLOADS":
        _reject("DpmWaveReportInput must use NO_RAW_PAYLOADS redaction policy.")

    validate_optional_portfolio_memory_context(
        payload=payload,
        evidence_portfolio_id=_single_portfolio_id(items),
        forbidden_field_names=FORBIDDEN_FIELD_NAMES,
        reject=_reject,
    )


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
        _reject(f"Wave PM memo payload requires object section `{key}`.")
    return cast(dict[str, Any], section)


def _require_string_list(section: dict[str, Any], key: str) -> list[str]:
    value = section.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _reject(f"Wave PM memo payload requires string-list field `{key}`.")
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
        detail=f"WAVE_PM_MEMO_GUARDRAIL_BLOCKED: {detail}",
    )
