from app.services.eval_catalog import build_evaluation_catalog


def test_evaluation_catalog_reports_evidence_categories_and_fixture_families() -> None:
    catalog = build_evaluation_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.delivery_phase == "foundation"
    assert catalog.manifest_version == "foundation.v1"
    assert any(category.category_id == "task_contract" for category in catalog.evidence_categories)
    assert any(category.category_id == "async_runtime" for category in catalog.evidence_categories)
    async_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "async_runtime_examples"
    )
    assert async_fixture.status == "STAGED"
    assert async_fixture.manifest_path == "docs/evals/fixtures/async.runtime/basic_cases.json"
    assert async_fixture.case_count == 3
    task_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "task_capability_contracts"
    )
    assert task_fixture.status == "STAGED"
    assert task_fixture.manifest_path == "docs/evals/fixtures/tasks.contracts/basic_cases.json"
    assert task_fixture.case_count == 2
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
    first_use_case_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "lotus_performance_first_use_case_examples"
    )
    assert first_use_case_fixture.status == "STAGED"
    assert (
        first_use_case_fixture.manifest_path
        == "docs/evals/fixtures/lotus-performance.first-use-case/basic_cases.json"
    )
    assert first_use_case_fixture.case_count == 2
    retrieval_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "retrieval_citation_examples"
    )
    assert retrieval_fixture.status == "STAGED"
    assert (
        retrieval_fixture.manifest_path == "docs/evals/fixtures/retrieval.search/basic_cases.json"
    )
    assert retrieval_fixture.case_count == 3
    retrieval_embedding_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "retrieval_embedding_examples"
    )
    assert retrieval_embedding_fixture.status == "STAGED"
    assert (
        retrieval_embedding_fixture.manifest_path
        == "docs/evals/fixtures/retrieval.embeddings/basic_cases.json"
    )
    assert retrieval_embedding_fixture.case_count == 2
    provider_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_policy_examples"
    )
    assert provider_fixture.status == "STAGED"
    assert provider_fixture.manifest_path == "docs/evals/fixtures/providers.policy/basic_cases.json"
    assert provider_fixture.case_count == 2
    provider_runtime_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_runtime_examples"
    )
    assert provider_runtime_fixture.status == "STAGED"
    assert (
        provider_runtime_fixture.manifest_path
        == "docs/evals/fixtures/providers.runtime/basic_cases.json"
    )
    assert provider_runtime_fixture.case_count == 2
    provider_failure_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_failure_mode_examples"
    )
    assert provider_failure_fixture.status == "STAGED"
    assert (
        provider_failure_fixture.manifest_path
        == "docs/evals/fixtures/providers.failure/basic_cases.json"
    )
    assert provider_failure_fixture.case_count == 2
    provider_operations_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_operations_examples"
    )
    assert provider_operations_fixture.status == "STAGED"
    assert (
        provider_operations_fixture.manifest_path
        == "docs/evals/fixtures/providers.operations/basic_cases.json"
    )
    assert provider_operations_fixture.case_count == 3
    provider_degradation_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_degradation_examples"
    )
    assert provider_degradation_fixture.status == "STAGED"
    assert (
        provider_degradation_fixture.manifest_path
        == "docs/evals/fixtures/providers.degradation/basic_cases.json"
    )
    assert provider_degradation_fixture.case_count == 3
    provider_embedding_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "provider_embedding_examples"
    )
    assert provider_embedding_fixture.status == "STAGED"
    assert (
        provider_embedding_fixture.manifest_path
        == "docs/evals/fixtures/providers.embeddings/basic_cases.json"
    )
    assert provider_embedding_fixture.case_count == 2
    safety_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "safety_policy_examples"
    )
    assert safety_fixture.status == "STAGED"
    assert safety_fixture.manifest_path == "docs/evals/fixtures/safety.policy/basic_cases.json"
    assert safety_fixture.case_count == 2
    safety_runtime_fixture = next(
        fixture
        for fixture in catalog.fixture_families
        if fixture.fixture_id == "safety_runtime_examples"
    )
    assert safety_runtime_fixture.status == "STAGED"
    assert (
        safety_runtime_fixture.manifest_path
        == "docs/evals/fixtures/safety.runtime/basic_cases.json"
    )
    assert safety_runtime_fixture.case_count == 4
