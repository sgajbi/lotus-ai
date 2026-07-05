from __future__ import annotations

from app.services.portfolio_memory_context_guardrails import (
    portfolio_memory_context_summary,
    validate_optional_portfolio_memory_context,
)
from tests.support.workflow_pack_fixtures import portfolio_memory_context_payload


class PortfolioMemoryRejected(Exception):
    pass


def _reject(detail: str) -> None:
    raise PortfolioMemoryRejected(detail)


def _payload_with_context(context: object) -> dict[str, object]:
    return {"portfolio_memory_context": context}


def _assert_rejected(context: object, expected_detail: str) -> None:
    try:
        validate_optional_portfolio_memory_context(
            payload=_payload_with_context(context),
            evidence_portfolio_id="PB_SG_GLOBAL_BAL_001",
            forbidden_field_names=frozenset({"raw_payload", "client_id"}),
            reject=_reject,
        )
    except PortfolioMemoryRejected as exc:
        assert expected_detail in str(exc)
    else:
        raise AssertionError("expected portfolio-memory guardrail rejection")


def test_portfolio_memory_context_guardrails_accept_absent_context() -> None:
    assert (
        validate_optional_portfolio_memory_context(
            payload={},
            evidence_portfolio_id="PB_SG_GLOBAL_BAL_001",
            forbidden_field_names=frozenset(),
            reject=_reject,
        )
        is None
    )


def test_portfolio_memory_context_guardrails_block_malformed_context_shapes() -> None:
    _assert_rejected("not-an-object", "must be an object")

    missing_context = portfolio_memory_context_payload()
    missing_context.pop("content_hash")
    _assert_rejected(missing_context, "Missing portfolio_memory_context fields")

    forbidden_context = portfolio_memory_context_payload()
    forbidden_context["nested"] = [{"raw_payload": {"unsafe": True}}]
    _assert_rejected(forbidden_context, "Forbidden portfolio memory fields present")


def test_portfolio_memory_context_guardrails_block_invalid_identity_and_counts() -> None:
    wrong_portfolio = portfolio_memory_context_payload(portfolio_id="OTHER_PORTFOLIO")
    _assert_rejected(wrong_portfolio, "portfolio_id must match")

    missing_hash = portfolio_memory_context_payload()
    missing_hash["content_hash"] = ""
    _assert_rejected(missing_hash, "requires a source content_hash")

    invalid_count = portfolio_memory_context_payload()
    invalid_count["event_count"] = -1
    _assert_rejected(invalid_count, "event_count must be a non-negative integer")

    missing_context_hash = portfolio_memory_context_payload()
    missing_context_hash["context_content_hash"] = ""
    _assert_rejected(missing_context_hash, "requires a context_content_hash")

    invalid_boundary = portfolio_memory_context_payload()
    invalid_boundary["support_boundary"] = ""
    _assert_rejected(invalid_boundary, "requires a support_boundary")


def test_portfolio_memory_context_guardrails_block_invalid_governance() -> None:
    invalid_sources = portfolio_memory_context_payload()
    invalid_sources["source_systems"] = ["lotus-manage", 99]
    _assert_rejected(invalid_sources, "requires string-list field `source_systems`")

    invalid_reasons = portfolio_memory_context_payload()
    invalid_reasons["reason_codes"] = "PORTFOLIO_MEMORY_READY"
    _assert_rejected(invalid_reasons, "requires string-list field `reason_codes`")

    missing_governance = portfolio_memory_context_payload()
    missing_governance["governance_policy"] = {}
    _assert_rejected(
        missing_governance, "Missing portfolio_memory_context governance_policy fields"
    )

    invalid_governance = portfolio_memory_context_payload()
    governance = invalid_governance["governance_policy"]
    assert isinstance(governance, dict)
    governance["redaction_policy"] = "RAW_PAYLOADS_ALLOWED"
    _assert_rejected(invalid_governance, "must enforce NO_RAW_PAYLOADS")

    missing_authority = portfolio_memory_context_payload()
    governance = missing_authority["governance_policy"]
    assert isinstance(governance, dict)
    governance["source_authority_policy"] = "source owned"
    _assert_rejected(missing_authority, "must carry source-authority")


def test_portfolio_memory_context_guardrails_block_invalid_event_refs() -> None:
    non_list_refs = portfolio_memory_context_payload()
    non_list_refs["event_refs"] = "not-a-list"
    _assert_rejected(non_list_refs, "event_refs must be a list")

    non_object_ref = portfolio_memory_context_payload()
    non_object_ref["event_refs"] = ["not-an-object"]
    _assert_rejected(non_object_ref, "event_refs[0] must be an object")

    missing_ref_fields = portfolio_memory_context_payload()
    missing_ref_fields["event_refs"] = [{}]
    _assert_rejected(missing_ref_fields, "Missing portfolio_memory_context event_refs[0] fields")

    raw_ref = portfolio_memory_context_payload()
    event_refs = raw_ref["event_refs"]
    assert isinstance(event_refs, list)
    first_ref = event_refs[0]
    assert isinstance(first_ref, dict)
    first_ref["redaction_policy"] = "RAW_PAYLOADS_ALLOWED"
    _assert_rejected(raw_ref, "event_refs[0] must enforce NO_RAW_PAYLOADS")

    missing_event_time = portfolio_memory_context_payload()
    event_refs = missing_event_time["event_refs"]
    assert isinstance(event_refs, list)
    first_ref = event_refs[0]
    assert isinstance(first_ref, dict)
    first_ref.pop("event_time")
    _assert_rejected(missing_event_time, "Missing portfolio_memory_context event_refs[0] fields")

    non_contiguous_rank = portfolio_memory_context_payload()
    event_refs = non_contiguous_rank["event_refs"]
    assert isinstance(event_refs, list)
    second_ref = event_refs[1]
    assert isinstance(second_ref, dict)
    second_ref["event_ref_selection_rank"] = 9
    _assert_rejected(non_contiguous_rank, "event_ref_selection_rank must be contiguous")

    mismatched_returned_count = portfolio_memory_context_payload()
    mismatched_returned_count["event_refs_returned"] = 1
    _assert_rejected(mismatched_returned_count, "event_refs_returned must match")

    mismatched_truncation = portfolio_memory_context_payload(event_ref_count=2)
    mismatched_truncation["event_count"] = 5
    mismatched_truncation["event_refs_omitted"] = 3
    mismatched_truncation["event_refs_truncated"] = False
    _assert_rejected(mismatched_truncation, "event_refs_truncated must match")


def test_portfolio_memory_context_summary_handles_unbounded_shapes() -> None:
    assert portfolio_memory_context_summary({}) == {
        "portfolio_memory_status": "not_supplied",
        "portfolio_memory_content_hash": "",
        "portfolio_memory_context_content_hash": "",
        "portfolio_memory_event_count": 0,
        "portfolio_memory_event_ref_count": 0,
        "portfolio_memory_event_refs_omitted": 0,
        "portfolio_memory_event_refs_truncated": False,
        "portfolio_memory_source_systems": [],
        "portfolio_memory_event_types": [],
        "portfolio_memory_supportability_state": "",
    }

    summary = portfolio_memory_context_summary(
        {
            "portfolio_memory_context": {
                "content_hash": "sha256:test",
                "context_content_hash": "sha256:context",
                "event_count": 1,
                "event_refs_omitted": 0,
                "event_refs_truncated": False,
                "source_systems": ["lotus-manage", 7],
                "event_refs": [{"event_type": "DPM_EXCEPTION"}, {"event_type": 42}, "bad-ref"],
                "supportability_state": "READY",
            }
        }
    )

    assert summary["portfolio_memory_status"] == "supplied"
    assert summary["portfolio_memory_source_systems"] == ["lotus-manage"]
    assert summary["portfolio_memory_event_types"] == ["DPM_EXCEPTION"]

    malformed_summary = portfolio_memory_context_summary(
        {
            "portfolio_memory_context": {
                "event_refs": "not-a-list",
                "source_systems": "lotus-manage",
            }
        }
    )
    assert malformed_summary["portfolio_memory_event_ref_count"] == 0
    assert malformed_summary["portfolio_memory_event_types"] == []
    assert malformed_summary["portfolio_memory_source_systems"] == []
