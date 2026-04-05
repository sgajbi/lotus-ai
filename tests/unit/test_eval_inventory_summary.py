from app.services.eval_catalog import build_evaluation_catalog
from app.services.eval_inventory_summary import summarize_evaluation_inventory


def test_summarize_evaluation_inventory_reports_fixture_and_case_counts() -> None:
    catalog = build_evaluation_catalog()

    summary = summarize_evaluation_inventory(catalog)

    assert summary.evidence_category_count == 6
    assert summary.staged_fixture_count >= 19
    assert summary.documented_fixture_count == 0
    assert summary.staged_case_count == 46
