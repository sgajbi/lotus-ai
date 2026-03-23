from app.services.eval_seam_summary import build_evaluation_seam_coverage


def test_evaluation_seam_coverage_reports_staged_fixtures_by_platform_boundary() -> None:
    seam_coverage = build_evaluation_seam_coverage()

    assert [item.seam_id for item in seam_coverage] == [
        "async_execution",
        "task_execution",
        "prompt_rollout",
        "retrieval",
        "provider_execution",
        "safety_execution",
    ]

    async_execution = seam_coverage[0]
    assert async_execution.staged_fixture_count == 1
    assert async_execution.staged_case_count == 3
    assert async_execution.fixture_ids == ["async_runtime_examples"]

    task_execution = seam_coverage[1]
    assert task_execution.staged_fixture_count == 3
    assert task_execution.staged_case_count == 6
    assert task_execution.fixture_ids == [
        "task_capability_contracts",
        "explanation_task_examples",
        "summarization_task_examples",
    ]

    prompt_rollout = seam_coverage[2]
    assert prompt_rollout.staged_fixture_count == 2
    assert prompt_rollout.staged_case_count == 2
    assert prompt_rollout.fixture_ids == [
        "prompt_promotion_examples",
        "prompt_rollback_examples",
    ]

    retrieval = seam_coverage[3]
    assert retrieval.staged_fixture_count == 1
    assert retrieval.staged_case_count == 3
    assert retrieval.fixture_ids == ["retrieval_citation_examples"]

    provider_execution = seam_coverage[4]
    assert provider_execution.staged_fixture_count == 5
    assert provider_execution.staged_case_count == 12
    assert provider_execution.fixture_ids == [
        "provider_policy_examples",
        "provider_runtime_examples",
        "provider_failure_mode_examples",
        "provider_operations_examples",
        "provider_degradation_examples",
    ]

    safety_execution = seam_coverage[5]
    assert safety_execution.staged_fixture_count == 2
    assert safety_execution.staged_case_count == 6
    assert safety_execution.fixture_ids == [
        "safety_policy_examples",
        "safety_runtime_examples",
    ]
