from __future__ import annotations

from typing import cast

from app.contracts.providers import ProviderExecutionRequest
from app.providers.proposal_memo_commentary_stub import (
    build_proposal_memo_commentary_stub_result,
)
from app.providers.stub_text_provider import StubTextProvider


def _context_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "memo_evidence": {
            "memo_id": "memo-prop-001-v3",
            "memo_hash": "sha256:memo-001",
            "memo_status": "ADVISOR_REVIEW_REQUIRED",
            "source_refs": [
                "lotus-advise:memo:memo-prop-001-v3",
                "lotus-core:portfolio:PB_SG_GLOBAL_BAL_001",
            ],
        },
        "commentary_request": {
            "requested_sections": [
                "EXECUTIVE_SUMMARY",
                "RISK_AND_SUITABILITY_LIMITATIONS",
            ],
        },
        "supportability": {
            "unsupported_claims": [
                "client_ready_publication",
                "suitability_approval",
                123,
            ],
        },
    }
    payload.update(overrides)
    return payload


def _provider_request(**overrides: object) -> ProviderExecutionRequest:
    payload: dict[str, object] = {
        "task_id": "explain.v1",
        "caller_app": "lotus-advise",
        "requested_by": "advisor.reviewer@lotus",
        "tenant_id": "tenant-sg-001",
        "prompt_version": "proposal-memo-commentary.v1",
        "system_instructions": "Draft bounded advisor-use commentary only.",
        "output_contract_notes": "Do not emit suitability approval or client-ready claims.",
        "output_label": "EXPLANATION_ONLY",
        "safety_mode": "documented_only",
        "redaction_posture": "MINIMIZATION_REQUIRED",
        "context_summary": "Draft advisor proposal memo commentary.",
        "context_payload": _context_payload(),
        "source_refs": ["lotus-advise:memo:memo-prop-001-v3"],
        "timeout_ms": 4000,
        "retry_limit": 0,
        "max_output_tokens": 512,
    }
    payload.update(overrides)
    return ProviderExecutionRequest.model_validate(payload)


def test_build_proposal_memo_commentary_stub_result_is_review_gated_and_bounded() -> None:
    result = build_proposal_memo_commentary_stub_result(
        context_payload=_context_payload(),
    )

    assert result is not None
    message, structured_output = result
    sections = cast(list[dict[str, str]], structured_output["sections"])

    assert message == (
        "Drafted review-gated advisor proposal memo commentary from bounded memo evidence "
        "for memo memo-prop-001-v3."
    )
    assert structured_output["workflow_pack_family"] == "proposal_memo_commentary"
    assert structured_output["narrative_type"] == "advisor_proposal_memo_commentary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "advisor_use_only"
    assert structured_output["memo_id"] == "memo-prop-001-v3"
    assert structured_output["memo_hash"] == "sha256:memo-001"
    assert structured_output["memo_status"] == "ADVISOR_REVIEW_REQUIRED"
    assert structured_output["source_ref_count"] == 2
    assert structured_output["section_count"] == 2
    assert structured_output["unsupported_claims"] == [
        "client_ready_publication",
        "suitability_approval",
    ]
    assert [section["section_key"] for section in sections] == [
        "EXECUTIVE_SUMMARY",
        "RISK_AND_SUITABILITY_LIMITATIONS",
    ]
    assert sections[0]["title"] == "Executive Summary"
    assert "bounded to the supplied memo evidence" in sections[0]["text"]
    assert "Current memo evidence posture is ADVISOR_REVIEW_REQUIRED" in sections[0]["text"]
    assert structured_output["review_guidance"] == [
        "Review generated commentary against the persisted memo hash before advisor use.",
        "Do not treat commentary as suitability, approval, client-ready publication, or evidence mutation.",
        "Escalate missing policy, fee, tax, conflict, or eligibility evidence instead of asking AI to infer it.",
    ]


def test_build_proposal_memo_commentary_stub_defaults_sections_and_ignores_invalid_refs() -> None:
    result = build_proposal_memo_commentary_stub_result(
        context_payload=_context_payload(
            memo_evidence={
                "memo_id": "memo-prop-002-v1",
                "memo_hash": "sha256:memo-002",
                "memo_status": "BLOCKED",
                "source_refs": "not-a-list",
            },
            commentary_request={"requested_sections": ["", 100]},
            supportability={"unsupported_claims": "not-a-list"},
        ),
    )

    assert result is not None
    _message, structured_output = result
    sections = cast(list[dict[str, str]], structured_output["sections"])

    assert structured_output["source_ref_count"] == 0
    assert structured_output["unsupported_claims"] == []
    assert structured_output["section_count"] == 2
    assert [section["section_key"] for section in sections] == [
        "EXECUTIVE_SUMMARY",
        "REVIEW_LIMITATIONS",
    ]
    assert all("Current memo evidence posture is BLOCKED" in section["text"] for section in sections)


def test_build_proposal_memo_commentary_stub_requires_memo_evidence_and_request() -> None:
    assert build_proposal_memo_commentary_stub_result(context_payload={}) is None
    assert (
        build_proposal_memo_commentary_stub_result(
            context_payload=_context_payload(memo_evidence=[]),
        )
        is None
    )
    assert (
        build_proposal_memo_commentary_stub_result(
            context_payload=_context_payload(commentary_request=[]),
        )
        is None
    )


def test_stub_text_provider_routes_proposal_memo_commentary_with_common_metadata() -> None:
    response = StubTextProvider().execute(_provider_request())
    structured_output = response.structured_output

    assert response.provider_id == "text.stub"
    assert response.stubbed is True
    assert response.failure_category is None
    assert structured_output["workflow_pack_family"] == "proposal_memo_commentary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "advisor_use_only"
    assert structured_output["provider_id"] == "text.stub"
    assert structured_output["adapter_kind"] == "STUB"
    assert structured_output["timeout_ms"] == 4000
    assert structured_output["retry_count"] == 0
    assert structured_output["max_output_tokens"] == 512
    assert structured_output["output_label"] == "EXPLANATION_ONLY"
    assert structured_output["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert structured_output["context_keys"] == [
        "commentary_request",
        "memo_evidence",
        "supportability",
    ]
    assert structured_output["source_refs"] == ["lotus-advise:memo:memo-prop-001-v3"]
    assert structured_output["stub_reason"] == (
        "lotus-ai emits deterministic governed proposal memo commentary posture "
        "before live provider rollout is enabled for this workflow pack."
    )
