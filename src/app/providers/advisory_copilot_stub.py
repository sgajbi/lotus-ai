from __future__ import annotations

from typing import Any


def build_advisory_copilot_stub_result(
    *,
    context_payload: dict[str, object],
    source_refs: list[str] | None = None,
) -> tuple[str, dict[str, object]] | None:
    evidence_packet = context_payload.get("copilot_evidence_packet")
    copilot_request = context_payload.get("copilot_request")
    supportability = context_payload.get("supportability")
    model_risk_controls = context_payload.get("model_risk_controls")
    if not (
        isinstance(evidence_packet, dict)
        and isinstance(copilot_request, dict)
        and isinstance(supportability, dict)
        and isinstance(model_risk_controls, dict)
    ):
        return None

    action_family = _as_str(copilot_request.get("action_family"))
    evidence_packet_id = _as_str(evidence_packet.get("evidence_packet_id"))
    evidence_packet_hash = _as_str(evidence_packet.get("evidence_packet_hash"))
    sections = _sections(
        evidence_packet.get("sections"),
        action_family=action_family,
        source_refs=source_refs or [],
    )
    unsupported_evidence = evidence_packet.get("unsupported_evidence")

    message = (
        "Drafted review-gated advisory copilot output from bounded evidence packet "
        f"{evidence_packet_id}."
    )
    structured_output: dict[str, object] = {
        "workflow_pack_family": _pack_family(action_family),
        "state": "REVIEW_REQUIRED",
        "scope": "advisor_and_reviewer_use_only",
        "action_family": action_family,
        "audience": _as_str(copilot_request.get("audience")),
        "evidence_packet_id": evidence_packet_id,
        "evidence_packet_hash": evidence_packet_hash,
        "sections": sections,
        "section_count": len(sections),
        "unsupported_evidence_count": (
            len(unsupported_evidence) if isinstance(unsupported_evidence, list) else 0
        ),
        "client_ready_publication": "BLOCKED",
        "human_review_required": True,
        "unsupported_claims": _string_list(supportability.get("unsupported_claims")),
        "model_risk": {
            "approved_provider_id": _as_str(model_risk_controls.get("approved_provider_id")),
            "approved_model_version": _as_str(model_risk_controls.get("approved_model_version")),
            "approved_instruction_set": _as_str(
                model_risk_controls.get("approved_instruction_set")
            ),
            "prompt_template_version": _as_str(model_risk_controls.get("prompt_template_version")),
            "output_schema_version": _as_str(model_risk_controls.get("output_schema_version")),
            "evaluation_pack_ref": _as_str(model_risk_controls.get("evaluation_pack_ref")),
        },
        "review_guidance": [
            "Review generated content against cited evidence before advisor use.",
            "Do not treat copilot output as policy approval, trade instruction, or client-ready communication.",
            "Escalate unavailable or restricted evidence instead of asking the copilot to infer it.",
        ],
    }
    return message, structured_output


def _sections(
    value: object,
    *,
    action_family: str,
    source_refs: list[str],
) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    sections: list[dict[str, object]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        section_key = _as_str(item.get("section_key"))
        title = _as_str(item.get("title"))
        section_source_refs = _section_source_refs(item.get("source_refs"), source_refs)
        if not section_key or not title or not section_source_refs:
            continue
        sections.append(
            {
                "section_key": section_key,
                "title": title,
                "text": (
                    f"{title}: Review the supplied source-backed evidence for this "
                    f"{action_family.lower().replace('_', ' ')} draft before advisor use."
                ),
                "claims": [
                    {
                        "claim_id": f"{section_key.lower()}_source_backed_review",
                        "claim_text": (
                            f"{title} is supported by the supplied governed source evidence."
                        ),
                        "source_refs": section_source_refs[:8],
                    }
                ],
            }
        )
    return sections


def _section_source_refs(value: object, source_refs: list[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    matched: list[str] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        source_system = _as_str(item.get("source_system"))
        source_type = _as_str(item.get("source_type"))
        content_hash = _source_ref_content_hash(item.get("content_hash"))
        if not source_system or not source_type:
            continue
        prefix = f"{source_system}:{source_type}:"
        suffix = f":{content_hash}"
        for source_ref in source_refs:
            if source_ref.startswith(prefix) and source_ref.endswith(suffix):
                matched.append(source_ref)
                break
    return matched


def _source_ref_content_hash(value: object) -> str:
    content_hash = _as_str(value)
    return content_hash or "no-content-hash"


def _pack_family(action_family: str) -> str:
    return f"advisory_copilot_{action_family.lower()}" if action_family else "advisory_copilot"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
