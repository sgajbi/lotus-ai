from app.services.eval_catalog import build_evaluation_catalog


def test_evaluation_catalog_reports_evidence_categories_and_fixture_families() -> None:
    catalog = build_evaluation_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.delivery_phase == "foundation"
    assert any(category.category_id == "task_contract" for category in catalog.evidence_categories)
    assert any(
        fixture.fixture_id == "task_capability_contracts" for fixture in catalog.fixture_families
    )
