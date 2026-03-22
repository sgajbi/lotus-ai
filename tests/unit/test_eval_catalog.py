from app.services.eval_catalog import build_evaluation_catalog


def test_evaluation_catalog_reports_evidence_categories_and_fixture_families() -> None:
    catalog = build_evaluation_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.delivery_phase == "foundation"
    assert catalog.manifest_version == "foundation.v1"
    assert any(category.category_id == "task_contract" for category in catalog.evidence_categories)
    explain_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "explanation_task_examples"
    )
    assert explain_fixture.status == "STAGED"
    assert explain_fixture.manifest_path == "docs/evals/fixtures/explain.v1/basic_cases.json"
    assert explain_fixture.case_count == 2
