from fastapi.testclient import TestClient

from app.services.eval_async_execution import run_next_evaluation_execution_job


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
        and fixture["case_count"] == 3
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
    assert body["staged_case_count"] == 26
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
    assert body["runtime_backed_run_count"] == 0
    assert body["historical_run_count"] == 2
    assert body["latest_recorded_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["latest_recorded_run_status"] == "RECORDED"
    assert body["evaluation_runner_active"] is True
    assert body["approval_gates"][0]["domain_id"] == "retrieval_execution"
    assert body["approval_gates"][1]["domain_id"] == "provider_execution"
    assert body["approval_gates"][0]["evidence_state"] == "STAGED_ONLY"


def test_evaluation_run_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/evals/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run_count"] == 2
    assert body["runtime_backed_run_count"] == 0
    assert body["historical_run_count"] == 2
    assert body["latest_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["status_counts"]["RECORDED"] == 1
    assert body["status_counts"]["SUPERSEDED"] == 1
    assert body["runs"][0]["record_source"] == "STAGED_ARTIFACT"
    assert body["runs"][0]["staged_case_count"] == 26
    assert body["runs"][1]["status"] == "SUPERSEDED"


def test_evaluation_run_detail_route(client: TestClient) -> None:
    response = client.get("/platform/evals/runs/foundation_eval_2026_03_22_001")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run"]["run_id"] == "foundation_eval_2026_03_22_001"
    assert body["run"]["record_source"] == "STAGED_ARTIFACT"
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
    assert response.json()["detail"] == "Evaluation run 'missing_run' was not found."


def test_evaluation_run_submit_route_accepts_runtime_backed_allowlisted_fixture(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/evals/runs/submit",
        json={
            "fixture_id": "retrieval_citation_examples",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-eval-submit-001",
            "triggered_by": "operator-a",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission_status"] == "ACCEPTED"
    assert body["accepted"] is True
    assert body["run_id"] is not None
    assert body["async_job_id"] is not None

    catalog_response = client.get("/platform/evals/runs")
    catalog_body = catalog_response.json()
    runtime_run = next(run for run in catalog_body["runs"] if run["run_id"] == body["run_id"])

    assert catalog_body["run_count"] == 3
    assert catalog_body["runtime_backed_run_count"] == 1
    assert runtime_run["record_source"] == "RUNTIME_STATE"
    assert runtime_run["fixture_id"] == "retrieval_citation_examples"
    assert runtime_run["status"] == "QUEUED"


def test_evaluation_run_detail_route_exposes_runtime_attempt_and_case_history(
    client: TestClient,
) -> None:
    submission = client.post(
        "/platform/evals/runs/submit",
        json={
            "fixture_id": "provider_policy_examples",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-eval-submit-003",
            "triggered_by": "operator-a",
        },
    ).json()

    run_next_evaluation_execution_job(worker_id="worker-a")

    detail_response = client.get(f"/platform/evals/runs/{submission['run_id']}")

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["run"]["record_source"] == "RUNTIME_STATE"
    assert body["run"]["status"] == "COMPLETED"
    assert body["attempts"][0]["status"] == "COMPLETED"
    assert body["attempts"][0]["verdict"] == "PASS"
    assert len(body["case_results"]) == 2
    assert body["case_results"][0]["outcome"] == "PASS"


def test_evaluation_run_submit_route_rejects_staged_only_fixture(client: TestClient) -> None:
    response = client.post(
        "/platform/evals/runs/submit",
        json={
            "fixture_id": "explanation_task_examples",
            "caller_app": "lotus-platform",
            "correlation_id": "corr-eval-submit-002",
            "triggered_by": "operator-a",
        },
    )

    assert response.status_code == 409
    assert "staged-only" in response.json()["detail"]


def test_evaluation_fixture_detail_route(client: TestClient) -> None:
    response = client.get("/platform/evals/fixtures/retrieval_citation_examples")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["manifest_version"] == "foundation.v1"
    assert body["fixture"]["fixture_id"] == "retrieval_citation_examples"
    assert body["task_id"] == "knowledge_search.v1"
    assert len(body["cases"]) == 3
    assert body["cases"][0]["case_id"] == "search_live_rfc_answer_preserves_citation"


def test_evaluation_fixture_detail_route_returns_not_found_for_unknown_fixture(
    client: TestClient,
) -> None:
    response = client.get("/platform/evals/fixtures/missing_fixture")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evaluation fixture family 'missing_fixture' was not found."
