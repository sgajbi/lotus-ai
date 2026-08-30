"""API contract for the review-gated accepted-output projection (issue #162).

The projection publishes the exact accepted `advisor_brief.pack@v1` narrative by
run id. These tests prove positive retrieval, every fail-closed posture, tenant
isolation without an existence oracle, hash stability, field minimization, and
the SQL restart proof the issue's evaluation condition demands.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.workflow_pack_fixtures import advisor_brief_task_execution_request_json

CALLER_HEADERS = {"X-Caller-App": "lotus-gateway", "X-Tenant-Id": "tenant-sg-001"}


def _execute_advisor_brief(client: TestClient, *, correlation_id: str) -> str:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(correlation_id=correlation_id),
    )
    assert execute_response.status_code == 200
    runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    return str(next(run["run_id"] for run in runs if run["correlation_id"] == correlation_id))


def _accept(client: TestClient, run_id: str, *, reviewed_by: str = "banker.sg.201") -> None:
    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": reviewed_by,
            "reason": "Accepted for accepted-output projection proof.",
        },
    )
    assert review_response.status_code == 200


def test_accepted_output_returns_the_exact_reviewed_narrative(client: TestClient) -> None:
    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-001")
    _accept(client, run_id, reviewed_by="banker.sg.201")

    response = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output",
        headers=CALLER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_id"] == "lotus-ai.workflow_pack_run.accepted_output.advisor_brief.v1"
    assert body["run_id"] == run_id
    assert body["pack_id"] == "advisor_brief.pack"
    assert body["pack_version"] == "v1"
    assert body["tenant_id"] == "tenant-sg-001"
    assert body["workflow_authority_owner"] == "lotus-gateway"
    assert body["review"]["reviewed_by"] == "banker.sg.201"
    assert body["review"]["reviewed_at"]
    assert body["grounded_summary"]
    assert body["talking_points"], "the reviewed talking points must be published"
    first_refs = body["talking_points"][0]["evidence_refs"]
    assert first_refs, "projected narrative items must keep their metric grounding"
    assert first_refs[0]["metric_label"]
    assert first_refs[0]["metric_value"]
    assert first_refs[0]["source_ref"] == "lotus-gateway:performance-summary:YTD"
    assert body["context"]["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
    assert body["context"]["period"] == "YTD"
    assert body["source_refs"] == ["lotus-gateway:performance-summary:YTD"]
    assert body["content_hash_algorithm"] == "sha256"
    assert len(body["content_hash"]) == 64

    # The published summary is the exact retained narrative, not a preview or a
    # regeneration: the consumer view's bounded preview is a prefix of it.
    consumer_view = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view").json()
    preview = consumer_view["provenance"]["output_preview"]
    assert body["grounded_summary"].startswith(preview[:64])


def test_accepted_output_is_byte_stable_across_retrievals(client: TestClient) -> None:
    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-002")
    _accept(client, run_id)

    first = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output", headers=CALLER_HEADERS
    )
    second = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output", headers=CALLER_HEADERS
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["content_hash"] == second.json()["content_hash"]


def test_accepted_output_excludes_internal_and_unprojected_fields(client: TestClient) -> None:
    """Field minimization: no storage references, no object-store paths, no raw
    structured-output spillover such as recommended_actions or grounded_facts."""

    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-003")
    _accept(client, run_id)

    response = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output", headers=CALLER_HEADERS
    )

    assert response.status_code == 200
    serialized = json.dumps(response.json())
    for forbidden in (
        "storage_reference",
        "object_key",
        "artifact://",
        "recommended_actions",
        "grounded_facts",
        "structured_output",
        "output_preview",
    ):
        assert forbidden not in serialized, forbidden


def test_awaiting_review_run_fails_closed(client: TestClient) -> None:
    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-004")

    response = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output", headers=CALLER_HEADERS
    )

    assert response.status_code == 409
    assert response.json()["metadata"]["reason_code"] == "run_not_accepted"


def test_rejected_run_fails_closed(client: TestClient) -> None:
    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-005")
    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "REJECT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.202",
            "reason": "Rejected for accepted-output projection proof.",
        },
    )
    assert review_response.status_code == 200

    response = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output", headers=CALLER_HEADERS
    )

    assert response.status_code == 409
    assert response.json()["metadata"]["reason_code"] == "run_not_accepted"


def test_revised_run_fails_closed_and_replacement_serves_content(client: TestClient) -> None:
    original_run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-006")
    replacement_run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-007")
    revise_response = client.post(
        f"/platform/workflow-packs/runs/{original_run_id}/review-actions",
        json={
            "action_type": "REVISE",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.203",
            "reason": "Revised for accepted-output projection proof.",
            "replacement_run_id": replacement_run_id,
        },
    )
    assert revise_response.status_code == 200
    _accept(client, replacement_run_id)

    superseded = client.get(
        f"/platform/workflow-packs/runs/{original_run_id}/accepted-output",
        headers=CALLER_HEADERS,
    )
    replacement = client.get(
        f"/platform/workflow-packs/runs/{replacement_run_id}/accepted-output",
        headers=CALLER_HEADERS,
    )

    assert superseded.status_code == 409
    assert superseded.json()["metadata"]["reason_code"] in {
        "run_not_accepted",
        "run_superseded",
    }
    assert replacement.status_code == 200
    assert replacement.json()["run_id"] == replacement_run_id


def test_wrong_tenant_and_unknown_run_share_one_not_found_shape(client: TestClient) -> None:
    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-008")
    _accept(client, run_id)

    wrong_tenant = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output",
        headers={"X-Caller-App": "lotus-gateway", "X-Tenant-Id": "tenant-uk-999"},
    )
    unknown_run = client.get(
        "/platform/workflow-packs/runs/wfr-does-not-exist/accepted-output",
        headers=CALLER_HEADERS,
    )

    assert wrong_tenant.status_code == unknown_run.status_code == 404
    # One shape: the wrong-tenant refusal must be indistinguishable from an
    # unknown run apart from the echoed identifier.
    wrong_detail = wrong_tenant.json()["detail"].replace(run_id, "{run_id}")
    unknown_detail = unknown_run.json()["detail"].replace("wfr-does-not-exist", "{run_id}")
    assert wrong_detail == unknown_detail


def test_unregistered_caller_is_refused(client: TestClient) -> None:
    run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-009")
    _accept(client, run_id)

    response = client.get(
        f"/platform/workflow-packs/runs/{run_id}/accepted-output",
        headers={"X-Caller-App": "unregistered-app", "X-Tenant-Id": "tenant-sg-001"},
    )

    assert response.status_code == 403


def test_missing_caller_headers_are_refused(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/wfr-any/accepted-output")

    assert response.status_code == 422


def test_openapi_names_the_review_gated_boundary(client: TestClient) -> None:
    schema = app.openapi()
    operation = schema["paths"]["/platform/workflow-packs/runs/{run_id}/accepted-output"]["get"]

    assert operation["operationId"] == "getWorkflowPackRunAcceptedOutput"
    description = operation["description"]
    assert "review-gated" in description
    assert "non-client-authoritative" in description
    assert "fails" in description and "closed" in description
    for status_code in ("200", "403", "404", "409", "422", "503"):
        assert status_code in operation["responses"]


def test_sql_backed_accepted_output_survives_restart_with_stable_hash(tmp_path: Path) -> None:
    """The issue's evaluation condition: execute, ACCEPT, restart, retrieve the
    exact run with a byte-stable canonical hash, reviewer identity and narrative."""

    database_url = f"sqlite:///{tmp_path / 'accepted-output-restart.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as client:
            run_id = _execute_advisor_brief(client, correlation_id="corr-accepted-output-sql-001")
            _accept(client, run_id, reviewed_by="banker.sg.sql.204")
            before_restart = client.get(
                f"/platform/workflow-packs/runs/{run_id}/accepted-output",
                headers=CALLER_HEADERS,
            )
            assert before_restart.status_code == 200

        with TestClient(app) as restarted_client:
            after_restart = restarted_client.get(
                f"/platform/workflow-packs/runs/{run_id}/accepted-output",
                headers=CALLER_HEADERS,
            )

        assert after_restart.status_code == 200
        assert after_restart.json() == before_restart.json()
        assert after_restart.json()["review"]["reviewed_by"] == "banker.sg.sql.204"
        assert after_restart.json()["content_hash"] == before_restart.json()["content_hash"]
