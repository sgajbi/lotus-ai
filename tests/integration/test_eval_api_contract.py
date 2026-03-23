from fastapi.testclient import TestClient


def test_evaluation_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/evals/catalog")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert any(
        category["category_id"] == "task_contract" for category in body["evidence_categories"]
    )
    assert any(
        category["category_id"] == "async_runtime" for category in body["evidence_categories"]
    )
    assert any(
        fixture["fixture_id"] == "async_runtime_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/async.runtime/basic_cases.json"
        and fixture["case_count"] == 3
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "task_capability_contracts"
        and fixture["manifest_path"] == "docs/evals/fixtures/tasks.contracts/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "explanation_task_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/explain.v1/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "summarization_task_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/summarize.v1/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "retrieval_citation_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/retrieval.search/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "provider_policy_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/providers.policy/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "provider_runtime_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/providers.runtime/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "provider_failure_mode_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/providers.failure/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "provider_operations_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/providers.operations/basic_cases.json"
        and fixture["case_count"] == 3
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "provider_degradation_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/providers.degradation/basic_cases.json"
        and fixture["case_count"] == 3
        for fixture in body["fixture_families"]
    )
    assert any(
        fixture["fixture_id"] == "safety_policy_examples"
        and fixture["manifest_path"] == "docs/evals/fixtures/safety.policy/basic_cases.json"
        and fixture["case_count"] == 2
        for fixture in body["fixture_families"]
    )


def test_evaluation_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/evals/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert body["evidence_category_count"] == 6
    assert body["staged_case_count"] == 25
    assert [item["seam_id"] for item in body["seam_coverage"]] == [
        "async_execution",
        "task_execution",
        "retrieval",
        "provider_execution",
        "safety_policy",
    ]
    assert body["seam_coverage"][0]["staged_fixture_count"] == 1
    assert body["seam_coverage"][0]["staged_case_count"] == 3
    assert body["seam_coverage"][1]["staged_fixture_count"] == 3
    assert body["seam_coverage"][1]["staged_case_count"] == 6
    assert body["seam_coverage"][3]["staged_fixture_count"] == 5
    assert body["seam_coverage"][3]["staged_case_count"] == 12
    assert body["recorded_run_count"] == 2
    assert body["latest_recorded_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["latest_recorded_run_status"] == "RECORDED"
    assert body["evaluation_runner_active"] is False


def test_evaluation_run_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/evals/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run_count"] == 2
    assert body["latest_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["status_counts"]["RECORDED"] == 1
    assert body["status_counts"]["SUPERSEDED"] == 1
    assert body["runs"][0]["staged_case_count"] == 25
    assert body["runs"][1]["status"] == "SUPERSEDED"


def test_evaluation_run_detail_route(client: TestClient) -> None:
    response = client.get("/platform/evals/runs/foundation_eval_2026_03_22_001")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run"]["run_id"] == "foundation_eval_2026_03_22_001"
    assert body["run"]["seam_coverage"][0]["seam_id"] == "async_execution"


def test_evaluation_run_detail_route_returns_superseded_artifact(client: TestClient) -> None:
    response = client.get("/platform/evals/runs/foundation_eval_2026_03_21_001")

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_id"] == "foundation_eval_2026_03_21_001"
    assert body["run"]["status"] == "SUPERSEDED"
    assert body["run"]["seam_coverage"][-1]["seam_id"] == "safety_policy"
    assert body["run"]["seam_coverage"][-1]["staged_fixture_count"] == 0


def test_evaluation_run_detail_route_returns_not_found_for_unknown_run(
    client: TestClient,
) -> None:
    response = client.get("/platform/evals/runs/missing_run")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evaluation run artifact 'missing_run' was not found."


def test_evaluation_fixture_detail_route(client: TestClient) -> None:
    response = client.get("/platform/evals/fixtures/retrieval_citation_examples")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert body["fixture"]["fixture_id"] == "retrieval_citation_examples"
    assert body["task_id"] == "retrieval.search.v1"
    assert len(body["cases"]) == 2
    assert body["cases"][0]["case_id"] == "search_rfc_answer_requires_citation"


def test_evaluation_fixture_detail_route_returns_not_found_for_unknown_fixture(
    client: TestClient,
) -> None:
    response = client.get("/platform/evals/fixtures/missing_fixture")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evaluation fixture family 'missing_fixture' was not found."
