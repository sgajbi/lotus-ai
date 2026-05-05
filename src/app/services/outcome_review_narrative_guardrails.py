from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, status

REQUIRED_AI_EVIDENCE_KEYS = frozenset(
    {
        "contract_version",
        "outcome_review_id",
        "outcome_review_content_hash",
        "portfolio_id",
        "proof_pack_id",
        "permitted_use",
        "forbidden_actions",
        "forbidden_fields_removed",
        "overall_outcome",
        "dimensions",
        "source_refs",
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
        "score_portfolio_manager",
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
        "pm_score",
        "recommend_trade",
    }
)
ALLOWED_REQUESTED_OUTPUTS = frozenset(
    {
        "pm_summary",
        "cio_summary",
        "control_summary",
        "operations_summary",
        "evidence_gaps",
    }
)


def validate_outcome_review_narrative_payload(payload: dict[str, object]) -> None:
    ai_evidence = _require_mapping(payload, "ai_evidence_input")
    missing = sorted(REQUIRED_AI_EVIDENCE_KEYS.difference(ai_evidence.keys()))
    if missing:
        _reject(f"Missing DpmOutcomeAiEvidenceInput fields: {', '.join(missing)}.")

    forbidden_fields = sorted(_find_forbidden_field_names(payload))
    if forbidden_fields:
        _reject(f"Forbidden AI evidence fields present: {', '.join(forbidden_fields)}.")

    forbidden_actions = _require_string_set(ai_evidence, "forbidden_actions")
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject(f"Missing required forbidden-action guardrails: {', '.join(missing_actions)}.")

    narrative_request = _require_mapping(payload, "narrative_request")
    requested_outputs = _require_string_set(narrative_request, "requested_outputs")
    unsupported_outputs = sorted(requested_outputs.difference(ALLOWED_REQUESTED_OUTPUTS))
    forbidden_outputs = sorted(requested_outputs.intersection(FORBIDDEN_REQUESTED_OUTPUTS))
    if forbidden_outputs:
        _reject(f"Forbidden narrative outputs requested: {', '.join(forbidden_outputs)}.")
    if unsupported_outputs:
        _reject(f"Unsupported narrative outputs requested: {', '.join(unsupported_outputs)}.")

    if not isinstance(ai_evidence.get("dimensions"), list) or not ai_evidence["dimensions"]:
        _reject("DpmOutcomeAiEvidenceInput must carry at least one bounded dimension.")
    if not isinstance(ai_evidence.get("source_refs"), list):
        _reject("DpmOutcomeAiEvidenceInput source_refs must be a list.")


def _require_mapping(payload: dict[str, object], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        _reject(f"Outcome-review narrative payload requires object section `{key}`.")
    return cast(dict[str, Any], value)


def _require_string_set(payload: dict[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _reject(f"Outcome-review narrative payload requires string-list field `{key}`.")
    return set(cast(list[str], value))


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
        detail=f"OUTCOME_REVIEW_NARRATIVE_GUARDRAIL_BLOCKED: {detail}",
    )
