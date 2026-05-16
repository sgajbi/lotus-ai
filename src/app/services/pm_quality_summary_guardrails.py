from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, status

from app.services.portfolio_memory_context_guardrails import (
    validate_optional_portfolio_memory_context,
)

REQUIRED_SCORE_RUN_KEYS = frozenset(
    {
        "product_name",
        "product_version",
        "score_run_id",
        "policy_id",
        "policy_version",
        "portfolio_manager_id",
        "as_of_date",
        "state",
        "reason_codes",
        "indicator_results",
        "source_refs",
        "content_hash",
    }
)
REQUIRED_SUPPORTABILITY_KEYS = frozenset(
    {
        "source_state",
        "requires_human_review",
        "forbidden_actions",
        "unsupported_claims",
    }
)
REQUIRED_FORBIDDEN_ACTIONS = frozenset(
    {
        "rank_portfolio_managers",
        "make_hr_decisions",
        "make_compensation_decisions",
        "enforce_conduct_action",
        "approve_rebalance",
        "contact_client",
        "place_orders",
        "invent_missing_evidence",
    }
)
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "account_number",
        "client_id",
        "client_name",
        "compensation_amount",
        "email",
        "hr_rating",
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
        "client_message",
        "compensation_recommendation",
        "conduct_action",
        "execution_instruction",
        "hr_rating",
        "pm_ranking",
        "trade_approval",
    }
)
ALLOWED_REQUESTED_OUTPUTS = frozenset(
    {
        "score_run_summary",
        "governance_summary",
        "evidence_gaps",
        "fairness_review_posture",
        "support_references",
    }
)


def validate_pm_quality_summary_payload(payload: dict[str, object]) -> None:
    score_run = _require_mapping(payload, "score_run")
    missing_score_run = sorted(REQUIRED_SCORE_RUN_KEYS.difference(score_run.keys()))
    if missing_score_run:
        _reject(f"Missing PmOperatingQualityScoreRun fields: {', '.join(missing_score_run)}.")

    if score_run.get("product_name") != "PmOperatingQualityScoreRun":
        _reject("score_run.product_name must be PmOperatingQualityScoreRun.")

    forbidden_fields = sorted(_find_forbidden_field_names(score_run))
    if forbidden_fields:
        _reject(f"Forbidden PM quality evidence fields present: {', '.join(forbidden_fields)}.")

    if (
        not isinstance(score_run.get("indicator_results"), list)
        or not score_run["indicator_results"]
    ):
        _reject("PmOperatingQualityScoreRun must carry at least one bounded indicator result.")
    if not isinstance(score_run.get("reason_codes"), list):
        _reject("PmOperatingQualityScoreRun reason_codes must be a list.")
    if not isinstance(score_run.get("source_refs"), list) or not score_run["source_refs"]:
        _reject("PmOperatingQualityScoreRun source_refs must be a non-empty list.")
    if "score" in score_run and not isinstance(
        score_run.get("score"), (str, int, float, type(None))
    ):
        _reject("score_run.score must be numeric, string, or null when supplied.")

    supportability = _require_mapping(payload, "supportability")
    missing_supportability = sorted(REQUIRED_SUPPORTABILITY_KEYS.difference(supportability.keys()))
    if missing_supportability:
        _reject(f"Missing PM quality supportability fields: {', '.join(missing_supportability)}.")
    forbidden_actions = _require_string_set(supportability, "forbidden_actions")
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject(f"Missing required forbidden-action guardrails: {', '.join(missing_actions)}.")

    summary_request = _require_mapping(payload, "summary_request")
    requested_outputs = _require_string_set(summary_request, "requested_outputs")
    forbidden_outputs = sorted(requested_outputs.intersection(FORBIDDEN_REQUESTED_OUTPUTS))
    unsupported_outputs = sorted(requested_outputs.difference(ALLOWED_REQUESTED_OUTPUTS))
    if forbidden_outputs:
        _reject(f"Forbidden PM quality summary outputs requested: {', '.join(forbidden_outputs)}.")
    if unsupported_outputs:
        _reject(
            f"Unsupported PM quality summary outputs requested: {', '.join(unsupported_outputs)}."
        )

    validate_optional_portfolio_memory_context(
        payload=payload,
        evidence_portfolio_id=score_run.get("portfolio_id"),
        forbidden_field_names=FORBIDDEN_FIELD_NAMES,
        reject=_reject,
    )


def _require_mapping(payload: dict[str, object], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        _reject(f"PM quality summary payload requires object section `{key}`.")
    return cast(dict[str, Any], value)


def _require_string_set(payload: dict[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _reject(f"PM quality summary payload requires string-list field `{key}`.")
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
        detail=f"PM_QUALITY_SUMMARY_GUARDRAIL_BLOCKED: {detail}",
    )
