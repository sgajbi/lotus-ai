from __future__ import annotations

from typing import cast

from fastapi import HTTPException, status

_FORBIDDEN_REQUESTED_OUTPUTS = {
    "approve_idea",
    "client_message",
    "client_ready_publication",
    "final_investment_recommendation",
    "portfolio_rebalance_instruction",
    "publish_to_client",
    "suitability_approval",
    "trade_or_order",
}

_ALLOWED_REQUESTED_OUTPUTS = {
    "advisor_review_summary",
    "evidence_gap_questions",
    "rationale_draft",
    "source_evidence_summary",
    "unsupported_claim_check",
}

_REQUIRED_UNSUPPORTED_CLAIMS = {
    "client_ready_publication",
    "final_investment_recommendation",
    "suitability_approval",
    "trade_or_order_action",
}

_REQUIRED_FORBIDDEN_ACTIONS = {
    "approve_suitability",
    "contact_client",
    "invent_missing_evidence",
    "make_final_recommendation",
    "place_orders",
}

_FORBIDDEN_TECHNICAL_KEYS = {
    "correlation_id",
    "prompt",
    "provider_response",
    "raw_payload",
    "raw_prompt",
    "raw_provider_output",
    "trace_id",
}


def validate_idea_explanation_payload(payload: dict[str, object]) -> None:
    redacted_evidence = _require_dict(payload, "redacted_evidence_packet")
    explanation_request = _require_dict(payload, "explanation_request")
    supportability = _require_dict(payload, "supportability")

    _reject_technical_keys(payload)
    _validate_redacted_evidence(redacted_evidence)
    _validate_explanation_request(explanation_request)
    _validate_supportability(supportability)


def _validate_redacted_evidence(redacted_evidence: dict[str, object]) -> None:
    required_keys = {
        "candidate_id",
        "evidence_content_hash",
        "evidence_packet_id",
        "family",
        "lifecycle_status",
        "reason_codes",
        "review_posture",
        "source_refs",
        "source_signal_count",
        "supportability",
    }
    missing = sorted(key for key in required_keys if not _has_value(redacted_evidence.get(key)))
    if missing:
        _reject("Idea explanation redacted evidence missing: " + ", ".join(missing))
    if not _as_str(redacted_evidence.get("evidence_content_hash")).startswith("sha256:"):
        _reject("Idea explanation evidence must carry a sha256 content hash.")

    source_refs = _require_list(
        redacted_evidence.get("source_refs"),
        "Idea explanation redacted evidence must include source refs.",
    )
    if not source_refs:
        _reject("Idea explanation redacted evidence must include source refs.")
    for source_ref in source_refs:
        if not isinstance(source_ref, dict):
            _reject("Idea explanation source refs must be structured objects.")
        source_ref_dict = cast(dict[str, object], source_ref)
        if not _as_str(source_ref_dict.get("source_system")):
            _reject("Idea explanation source refs must include source_system.")
        if not _as_str(source_ref_dict.get("product_id")):
            _reject("Idea explanation source refs must include product_id.")


def _validate_explanation_request(explanation_request: dict[str, object]) -> None:
    if not _as_str(explanation_request.get("request_id")):
        _reject("Idea explanation request must include request_id.")
    if _as_str(explanation_request.get("workflow_pack_id")) not in {
        "lotus-ai:idea-explanation:v1",
        "idea_explanation.pack",
    }:
        _reject("Idea explanation request must identify the Idea workflow pack.")
    requested_outputs = _require_list(
        explanation_request.get("requested_outputs"),
        "Idea explanation request must include bounded requested_outputs.",
    )
    requested_output_set = {_as_str(item) for item in requested_outputs}
    forbidden = sorted(_FORBIDDEN_REQUESTED_OUTPUTS.intersection(requested_output_set))
    if forbidden:
        _reject("Forbidden Idea explanation outputs requested: " + ", ".join(forbidden))
    unsupported = sorted(requested_output_set.difference(_ALLOWED_REQUESTED_OUTPUTS))
    if unsupported:
        _reject("Unsupported Idea explanation outputs requested: " + ", ".join(unsupported))


def _validate_supportability(supportability: dict[str, object]) -> None:
    if supportability.get("human_review_required") is not True:
        _reject("Idea explanation output must require human review.")
    if _as_str(supportability.get("client_ready_publication")) != "BLOCKED":
        _reject("Idea explanation supportability must block client-ready publication.")
    unsupported_claims = {
        _as_str(item)
        for item in _require_list(
            supportability.get("unsupported_claims"),
            "Idea explanation supportability must include unsupported claims.",
        )
    }
    missing_claims = sorted(_REQUIRED_UNSUPPORTED_CLAIMS.difference(unsupported_claims))
    if missing_claims:
        _reject(
            "Idea explanation supportability missing unsupported claims: "
            + ", ".join(missing_claims)
        )
    forbidden_actions = {
        _as_str(item)
        for item in _require_list(
            supportability.get("forbidden_actions"),
            "Idea explanation supportability must include forbidden actions.",
        )
    }
    missing_actions = sorted(_REQUIRED_FORBIDDEN_ACTIONS.difference(forbidden_actions))
    if missing_actions:
        _reject(
            "Idea explanation supportability missing forbidden actions: "
            + ", ".join(missing_actions)
        )


def _reject_technical_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_TECHNICAL_KEYS:
                _reject(f"Idea explanation payload cannot include technical field `{key}`.")
            _reject_technical_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_technical_keys(child)


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        _reject(f"Idea explanation payload requires `{key}`.")
    return cast(dict[str, object], value)


def _require_list(value: object, detail: str) -> list[object]:
    if not isinstance(value, list):
        _reject(detail)
    return cast(list[object], value)


def _has_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


def _reject(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _as_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
