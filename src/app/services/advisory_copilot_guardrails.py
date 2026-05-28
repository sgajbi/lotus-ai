from __future__ import annotations

from typing import cast

from fastapi import HTTPException, status

_FORBIDDEN_REQUESTED_OUTPUTS = {
    "approve_advice",
    "approve_policy",
    "client_message",
    "client_ready_publication",
    "order_ticket",
    "place_order",
    "trade_instruction",
    "waive_policy",
}

_FORBIDDEN_TECHNICAL_KEYS = {
    "correlation_id",
    "provider_response",
    "raw_payload",
    "raw_prompt",
    "trace_id",
}


def validate_advisory_copilot_payload(payload: dict[str, object]) -> None:
    evidence_packet = _require_dict(payload, "copilot_evidence_packet")
    copilot_request = _require_dict(payload, "copilot_request")
    supportability = _require_dict(payload, "supportability")
    model_risk_controls = _require_dict(payload, "model_risk_controls")

    _reject_technical_keys(payload)
    _validate_evidence_packet(evidence_packet)
    _validate_request(copilot_request)
    _validate_supportability(supportability)
    _validate_model_risk_controls(model_risk_controls)


def _validate_evidence_packet(evidence_packet: dict[str, object]) -> None:
    if _as_str(evidence_packet.get("evidence_packet_hash")).startswith("sha256:") is False:
        _reject("Advisory copilot evidence packet must carry a sha256 content hash.")
    if _as_str(evidence_packet.get("client_ready_publication")) != "BLOCKED":
        _reject("Advisory copilot evidence packet must keep client-ready publication blocked.")

    sections = _require_list(
        evidence_packet.get("sections"),
        "Advisory copilot evidence packet sections must be supplied as a list.",
    )
    unsupported_evidence = evidence_packet.get("unsupported_evidence")
    if unsupported_evidence is not None and not isinstance(unsupported_evidence, list):
        _reject("Advisory copilot unsupported evidence must be supplied as a list.")

    source_ref_count = 0
    for section in sections:
        if not isinstance(section, dict):
            _reject("Advisory copilot evidence sections must be structured objects.")
        section_dict = cast(dict[str, object], section)
        source_refs = section_dict.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            _reject("Advisory copilot evidence sections must carry source refs.")
        source_ref_count += len(cast(list[object], source_refs))
    if source_ref_count == 0:
        _reject("Advisory copilot evidence packet must include source-backed evidence.")


def _validate_request(copilot_request: dict[str, object]) -> None:
    if not _as_str(copilot_request.get("action_family")):
        _reject("Advisory copilot request must include an action family.")
    if not _as_str(copilot_request.get("audience")):
        _reject("Advisory copilot request must include an audience.")

    requested_outputs = _require_list(
        copilot_request.get("requested_outputs"),
        "Advisory copilot request must include bounded requested outputs.",
    )
    if not requested_outputs:
        _reject("Advisory copilot request must include bounded requested outputs.")
    forbidden = sorted(
        output
        for output in (_as_str(item) for item in requested_outputs)
        if output in _FORBIDDEN_REQUESTED_OUTPUTS
    )
    if forbidden:
        _reject(f"Forbidden advisory copilot outputs requested: {', '.join(forbidden)}")


def _validate_supportability(supportability: dict[str, object]) -> None:
    if supportability.get("human_review_required") is not True:
        _reject("Advisory copilot output must require human review.")
    if _as_str(supportability.get("client_ready_publication")) != "BLOCKED":
        _reject("Advisory copilot supportability must block client-ready publication.")
    unsupported_claims = _require_list(
        supportability.get("unsupported_claims"),
        "Advisory copilot supportability must include unsupported claims.",
    )
    required_claims = {"client_ready_publication", "policy_approval", "trade_or_order_action"}
    if not required_claims.issubset({_as_str(item) for item in unsupported_claims}):
        _reject("Advisory copilot supportability is missing required unsupported claims.")


def _validate_model_risk_controls(model_risk_controls: dict[str, object]) -> None:
    required_keys = {
        "approved_instruction_set",
        "evaluation_pack_ref",
        "output_schema_version",
        "prompt_template_version",
    }
    missing = sorted(key for key in required_keys if not _as_str(model_risk_controls.get(key)))
    if missing:
        _reject(f"Advisory copilot model-risk controls missing: {', '.join(missing)}")


def _reject_technical_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_TECHNICAL_KEYS:
                _reject(f"Advisory copilot payload cannot include technical field `{key}`.")
            _reject_technical_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_technical_keys(child)


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        _reject(f"Advisory copilot payload requires `{key}`.")
    return cast(dict[str, object], value)


def _require_list(value: object, detail: str) -> list[object]:
    if not isinstance(value, list):
        _reject(detail)
    return cast(list[object], value)


def _reject(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _as_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
