from app.services.eval_seam_summary import build_evaluation_seam_coverage


def test_evaluation_seam_coverage_reports_staged_fixtures_by_platform_boundary() -> None:
    seam_coverage = build_evaluation_seam_coverage()

    assert [item.seam_id for item in seam_coverage] == [
        "task_execution",
        "retrieval",
        "provider_execution",
        "safety_policy",
    ]

    task_execution = seam_coverage[0]
    assert task_execution.staged_fixture_count == 3
    assert task_execution.staged_case_count == 6
    assert task_execution.fixture_ids == [
        "task_capability_contracts",
        "explanation_task_examples",
        "summarization_task_examples",
    ]

    retrieval = seam_coverage[1]
    assert retrieval.staged_fixture_count == 1
    assert retrieval.staged_case_count == 2
    assert retrieval.fixture_ids == ["retrieval_citation_examples"]

    provider_execution = seam_coverage[2]
    assert provider_execution.staged_fixture_count == 5
    assert provider_execution.staged_case_count == 10
    assert provider_execution.fixture_ids == [
        "provider_policy_examples",
        "provider_runtime_examples",
        "provider_failure_mode_examples",
        "provider_operations_examples",
        "provider_degradation_examples",
    ]
