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
    summarize_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "summarization_task_examples"
    )
    assert summarize_fixture.status == "STAGED"
    assert summarize_fixture.manifest_path == "docs/evals/fixtures/summarize.v1/basic_cases.json"
    assert summarize_fixture.case_count == 2
    retrieval_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "retrieval_citation_examples"
    )
    assert retrieval_fixture.status == "STAGED"
    assert (
        retrieval_fixture.manifest_path == "docs/evals/fixtures/retrieval.search/basic_cases.json"
    )
    assert retrieval_fixture.case_count == 2
    provider_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_policy_examples"
    )
    assert provider_fixture.status == "STAGED"
    assert provider_fixture.manifest_path == "docs/evals/fixtures/providers.policy/basic_cases.json"
    assert provider_fixture.case_count == 2
    safety_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "safety_policy_examples"
    )
    assert safety_fixture.status == "STAGED"
    assert safety_fixture.manifest_path == "docs/evals/fixtures/safety.policy/basic_cases.json"
    assert safety_fixture.case_count == 2
