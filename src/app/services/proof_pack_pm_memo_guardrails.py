from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException, status

REQUIRED_AI_EVIDENCE_KEYS = frozenset(
    {
        "contract_version",
        "proof_pack_id",
        "proof_pack_content_hash",
        "portfolio_id",
        "as_of_date",
        "permitted_use",
        "forbidden_actions",
        "forbidden_fields_removed",
        "decision_summary",
        "supportability_status",
        "reason_codes",
        "sections",
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
        "pm_memo",
        "rationale_summary",
        "approval_checklist",
        "risk_caveats",
        "operations_handoff",
        "evidence_gaps",
    }
)


def validate_proof_pack_pm_memo_payload(payload: dict[str, object]) -> None:
    ai_evidence = _require_object_section(payload, "ai_evidence_input")
    memo_request = _require_object_section(payload, "memo_request")
    _require_object_section(payload, "supportability")

    missing_evidence = sorted(REQUIRED_AI_EVIDENCE_KEYS.difference(ai_evidence.keys()))
    if missing_evidence:
        _reject("Missing DpmProofPackAiEvidenceInput fields: " + ", ".join(missing_evidence))

    forbidden_fields = sorted(_find_forbidden_field_names(ai_evidence))
    if forbidden_fields:
        _reject("Forbidden AI evidence fields present: " + ", ".join(forbidden_fields))

    forbidden_actions = _require_string_list(ai_evidence, "forbidden_actions")
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject("Missing required forbidden-action guardrails: " + ", ".join(missing_actions))

    requested_outputs = set(_require_string_list(memo_request, "requested_outputs"))
    forbidden_outputs = sorted(FORBIDDEN_REQUESTED_OUTPUTS.intersection(requested_outputs))
    if forbidden_outputs:
        _reject("Forbidden memo outputs requested: " + ", ".join(forbidden_outputs))
    unsupported_outputs = sorted(requested_outputs.difference(ALLOWED_REQUESTED_OUTPUTS))
    if unsupported_outputs:
        _reject("Unsupported memo outputs requested: " + ", ".join(unsupported_outputs))

    sections = ai_evidence.get("sections")
    if not isinstance(sections, list) or not sections:
        _reject("DpmProofPackAiEvidenceInput requires at least one bounded section.")
    source_refs = ai_evidence.get("source_refs")
    if not isinstance(source_refs, list):
        _reject("DpmProofPackAiEvidenceInput source_refs must be a list.")


def _require_object_section(payload: dict[str, object], key: str) -> dict[str, Any]:
    section = payload.get(key)
    if not isinstance(section, dict):
        _reject(f"Proof-pack PM memo payload requires object section `{key}`.")
    return cast(dict[str, Any], section)


def _require_string_list(section: dict[str, Any], key: str) -> list[str]:
    value = section.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _reject(f"Proof-pack PM memo payload requires string-list field `{key}`.")
    return cast(list[str], value)


def _find_forbidden_field_names(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in FORBIDDEN_FIELD_NAMES:
                found.add(key.lower())
            found.update(_find_forbidden_field_names(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_field_names(item))
    return found


def _reject(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"PROOF_PACK_PM_MEMO_GUARDRAIL_BLOCKED: {detail}",
    )
