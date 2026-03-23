from fastapi import HTTPException

from app.services.eval_fixture_service import build_evaluation_fixture_detail


def test_evaluation_fixture_detail_returns_case_metadata_for_staged_fixture() -> None:
    detail = build_evaluation_fixture_detail(fixture_id="retrieval_citation_examples")

    assert detail.service == "lotus-ai"
    assert detail.manifest_version == "foundation.v1"
    assert detail.fixture.fixture_id == "retrieval_citation_examples"
    assert detail.task_id == "knowledge_search.v1"
    assert len(detail.cases) == 3
    assert detail.cases[0].case_id == "search_live_rfc_answer_preserves_citation"


def test_evaluation_fixture_detail_raises_not_found_for_unknown_fixture() -> None:
    try:
        build_evaluation_fixture_detail(fixture_id="missing_fixture")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Evaluation fixture family 'missing_fixture' was not found."
    else:
        raise AssertionError("Expected fixture lookup to raise HTTPException.")
