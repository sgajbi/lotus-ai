"""API contract for the latest-accepted lookup (issue #183).

These tests prove the two-step consumer flow the report ordering surface
depends on - resolve latest accepted identity, then fetch the narrative by
run_id - plus the bounded not-found reasons, review-recency determinism,
tenant isolation without an existence oracle, caller authorization, and that
the literal `accepted-latest` path is never captured as a run id.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.support.workflow_pack_fixtures import advisor_brief_task_execution_request_json

CALLER_HEADERS = {"X-Caller-App": "lotus-gateway", "X-Tenant-Id": "tenant-sg-001"}
LOOKUP_PATH = "/platform/workflow-packs/runs/accepted-latest"


def _execute_advisor_brief(
    client: TestClient, *, correlation_id: str, portfolio_id: str = "PB_SG_GLOBAL_BAL_001"
) -> str:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id=correlation_id, portfolio_id=portfolio_id
        ),
    )
    assert execute_response.status_code == 200
    runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    return str(next(run["run_id"] for run in runs if run["correlation_id"] == correlation_id))


def _accept(client: TestClient, run_id: str, *, reviewed_by: str = "banker.sg.301") -> None:
    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": reviewed_by,
            "reason": "Accepted for latest-accepted lookup proof.",
        },
    )
    assert review_response.status_code == 200


def _lookup_params(**overrides: str) -> dict[str, str]:
    params = {"pack_family": "advisor_brief", "portfolio_id": "PB_SG_GLOBAL_BAL_001"}
    params.update(overrides)
    return params


def test_accepted_latest_resolves_the_most_recently_accepted_run(
    client: TestClient,
) -> None:
    """Two accepted runs for one portfolio: the lookup answers with the run
    accepted LAST, and the envelope chains to the run_id narrative surface."""

    first_run = _execute_advisor_brief(client, correlation_id="corr-accepted-latest-001")
    second_run = _execute_advisor_brief(client, correlation_id="corr-accepted-latest-002")
    _accept(client, first_run, reviewed_by="banker.sg.301")
    _accept(client, second_run, reviewed_by="banker.sg.302")

    response = client.get(LOOKUP_PATH, params=_lookup_params(), headers=CALLER_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["schema_id"] == "lotus-ai.workflow_pack_run.accepted_latest.v1"
    assert body["run_id"] == second_run
    assert body["pack_id"] == "advisor_brief.pack"
    assert body["pack_family"] == "advisor_brief"
    assert body["pack_version"] == "v1"
    assert body["tenant_id"] == "tenant-sg-001"
    assert body["review"]["reviewed_by"] == "banker.sg.302"
    assert body["context"]["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
    assert (
        body["accepted_output_schema_id"]
        == "lotus-ai.workflow_pack_run.accepted_output.advisor_brief.v1"
    )

    # Identity envelope only: none of the narrative fields leak here.
    for narrative_field in (
        "grounded_summary",
        "talking_points",
        "risks_and_exceptions",
        "source_refs",
    ):
        assert narrative_field not in body

    # The two-step consumer flow: the resolved run_id fetches the narrative,
    # and the envelope's content hash pins exactly that content.
    narrative = client.get(
        f"/platform/workflow-packs/runs/{body['run_id']}/accepted-output",
        headers=CALLER_HEADERS,
    )
    assert narrative.status_code == 200
    assert narrative.json()["content_hash"] == body["content_hash"]
    assert narrative.json()["grounded_summary"]


def test_accepted_latest_ignores_unaccepted_and_foreign_portfolio_runs(
    client: TestClient,
) -> None:
    """A completed-but-unreviewed run and an accepted run for another
    portfolio both leave the requested portfolio unanswered: no_accepted_run."""

    _execute_advisor_brief(
        client, correlation_id="corr-accepted-latest-010", portfolio_id="PB_SG_TARGET_010"
    )
    other_portfolio_run = _execute_advisor_brief(
        client, correlation_id="corr-accepted-latest-011", portfolio_id="PB_SG_OTHER_011"
    )
    _accept(client, other_portfolio_run)

    response = client.get(
        LOOKUP_PATH,
        params=_lookup_params(portfolio_id="PB_SG_TARGET_010"),
        headers=CALLER_HEADERS,
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "LOTUS_AI_ACCEPTED_LATEST_NO_ACCEPTED_RUN"
    assert body["metadata"]["reason_code"] == "no_accepted_run"


def test_accepted_latest_distinguishes_context_mismatch_from_absence(
    client: TestClient,
) -> None:
    """The generated brief asserts no as_of_date, so an as_of_date filter can
    never match it: no_context_match, proving unasserted context is not a
    wildcard at the API boundary."""

    run_id = _execute_advisor_brief(
        client, correlation_id="corr-accepted-latest-020", portfolio_id="PB_SG_FILTERED_020"
    )
    _accept(client, run_id)

    response = client.get(
        LOOKUP_PATH,
        params=_lookup_params(portfolio_id="PB_SG_FILTERED_020", as_of_date="2026-04-22"),
        headers=CALLER_HEADERS,
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "LOTUS_AI_ACCEPTED_LATEST_NO_CONTEXT_MATCH"
    assert body["metadata"]["reason_code"] == "no_context_match"


def test_accepted_latest_does_not_leak_existence_across_tenants(
    client: TestClient,
) -> None:
    run_id = _execute_advisor_brief(
        client, correlation_id="corr-accepted-latest-030", portfolio_id="PB_SG_TENANT_030"
    )
    _accept(client, run_id)

    response = client.get(
        LOOKUP_PATH,
        params=_lookup_params(portfolio_id="PB_SG_TENANT_030"),
        headers={"X-Caller-App": "lotus-gateway", "X-Tenant-Id": "tenant-uk-999"},
    )

    assert response.status_code == 404
    assert response.json()["metadata"]["reason_code"] == "no_accepted_run"


def test_accepted_latest_refuses_unsupported_pack_family(client: TestClient) -> None:
    response = client.get(
        LOOKUP_PATH,
        params=_lookup_params(pack_family="fund_teaser"),
        headers=CALLER_HEADERS,
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "LOTUS_AI_ACCEPTED_LATEST_PACK_PROJECTION_UNSUPPORTED"
    assert body["metadata"]["reason_code"] == "pack_projection_unsupported"


def test_accepted_latest_requires_a_registered_caller(client: TestClient) -> None:
    response = client.get(
        LOOKUP_PATH,
        params=_lookup_params(),
        headers={"X-Caller-App": "unknown-app", "X-Tenant-Id": "tenant-sg-001"},
    )

    assert response.status_code == 403


def test_accepted_latest_literal_path_is_not_captured_as_a_run_id(
    client: TestClient,
) -> None:
    """The literal segment must reach the lookup route: its bounded
    problem-details shape proves the {run_id} detail route never captured it."""

    response = client.get(LOOKUP_PATH, params=_lookup_params(), headers=CALLER_HEADERS)

    assert response.status_code in {200, 404}
    if response.status_code == 404:
        assert response.json()["metadata"]["reason_code"] in {
            "no_accepted_run",
            "no_context_match",
        }


def test_accepted_latest_names_the_lookup_boundary(client: TestClient) -> None:
    from app.main import app

    schema = app.openapi()
    operation = schema["paths"][LOOKUP_PATH]["get"]

    assert operation["operationId"] == "getWorkflowPackRunAcceptedLatest"
    description = operation["description"]
    assert "accepting review" in description
    assert "wildcard" in description
    assert "existence oracle" in description
    for status_code in ("200", "403", "404", "409", "422", "503"):
        assert status_code in operation["responses"]


def test_accepted_latest_store_unavailable_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.workflow_pack_run_ledger import WorkflowPackRunStoreUnavailableError

    def raise_store_unavailable() -> None:
        raise WorkflowPackRunStoreUnavailableError("Workflow-pack run store is not ready.")

    monkeypatch.setattr(
        "app.services.workflow_pack_run_accepted_latest.ensure_workflow_pack_run_store_ready",
        raise_store_unavailable,
    )

    response = client.get(LOOKUP_PATH, params=_lookup_params(), headers=CALLER_HEADERS)

    assert response.status_code == 503
