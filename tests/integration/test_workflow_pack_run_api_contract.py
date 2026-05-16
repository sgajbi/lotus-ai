from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import app
from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.workflow_pack_fixtures import (
    advisor_brief_task_execution_request_json,
    advisor_brief_workflow_pack_execution_request_json,
    dpm_exception_summary_workflow_pack_execution_request_json,
    outcome_review_narrative_workflow_pack_execution_request_json,
    pm_quality_summary_workflow_pack_execution_request_json,
    proof_pack_pm_memo_workflow_pack_execution_request_json,
    twr_inspection_support_brief_workflow_pack_execution_request_json,
    wave_pm_memo_workflow_pack_execution_request_json,
    workspace_rationale_workflow_pack_execution_request_json,
)


def _assert_task_flow_recorded_for_run(
    *,
    client: TestClient,
    run_id: str,
    expected_status: str = "WAITING_FOR_REVIEW",
) -> None:
    catalog_response = client.get("/platform/workflow-packs/task-flows")
    assert catalog_response.status_code == 200
    task_flows = catalog_response.json()["task_flows"]
    matching = [flow for flow in task_flows if run_id in flow["run_refs"]]
    assert len(matching) == 1
    task_flow = matching[0]
    assert task_flow["flow_status"] == expected_status
    assert task_flow["runtime_states"][run_id] in {"COMPLETED", "FAILED"}
    assert task_flow["review_states"][run_id] == "AWAITING_REVIEW"

    detail_response = client.get(f"/platform/workflow-packs/task-flows/{task_flow['task_flow_id']}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["task_flow"]["run_refs"] == [run_id]
    assert detail_body["checkpoints"][0]["run_id"] == run_id


def test_workflow_pack_run_catalog_starts_empty(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["run_store_mode"] == "memory"
    assert body["run_count"] == 0
    assert body["filters_applied"] == {"limit": 100}
    assert body["ready_count"] == 0
    assert body["action_required_count"] == 0
    assert body["historical_count"] == 0
    assert body["runs"] == []


def test_workflow_pack_run_catalog_and_detail_record_advisor_brief_execution(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(correlation_id="corr-pack-run-api-001"),
    )
    assert execute_response.status_code == 200

    catalog_response = client.get("/platform/workflow-packs/runs")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["run_count"] == 1
    assert catalog_body["filters_applied"] == {"limit": 100}
    assert catalog_body["awaiting_review_count"] == 1
    assert catalog_body["completed_count"] == 1
    assert catalog_body["ready_count"] == 0
    assert catalog_body["action_required_count"] == 1
    assert catalog_body["historical_count"] == 0
    run = catalog_body["runs"][0]
    assert run["pack_id"] == "advisor_brief.pack"
    assert run["registration_ref"] == "advisor_brief.pack@v1"
    assert run["runtime_state"] == "COMPLETED"
    assert run["review_state"] == "AWAITING_REVIEW"
    assert run["supportability_status"] == "ACTION_REQUIRED"
    assert run["allowed_review_actions"] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert run["review_summary"]["latest_review_event_at"] is None
    assert run["review_summary"]["latest_review_actor"] is None
    assert run["review_summary"]["review_transition_count"] == 0
    assert run["review_summary"]["has_review_history"] is False
    assert len(run["artifact_refs"]) == 1
    assert run["artifact_refs"][0]["domain"] == "workflow_pack"
    assert run["artifact_refs"][0]["artifact_type"] == "run_output_summary"

    detail_response = client.get(f"/platform/workflow-packs/runs/{run['run_id']}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["run_id"] == run["run_id"]
    assert detail_body["review"]["state"] == "AWAITING_REVIEW"
    assert detail_body["review"]["latest_review_event_at"] is None
    assert detail_body["review"]["latest_review_actor"] is None
    assert detail_body["review"]["review_transition_count"] == 0
    assert detail_body["review"]["has_review_history"] is False
    assert detail_body["provenance"]["artifact_ref_count"] == 1
    assert detail_body["provenance"]["artifact_types"] == ["run_output_summary"]
    assert detail_body["provenance"]["evidence_descriptor_count"] >= 1
    assert "task_contract" in detail_body["provenance"]["evidence_types"]
    assert detail_body["supportability"]["status"] == "ACTION_REQUIRED"
    assert detail_body["supportability"]["review_pending"] is True
    assert detail_body["run"]["artifact_refs"][0]["source_object_id"] == run["run_id"]
    assert detail_body["events"][0]["event_type"] == "RUN_RECORDED"
    assert detail_body["run"]["workflow_surface"] == "advisor-brief-workspace"
    _assert_task_flow_recorded_for_run(client=client, run_id=run["run_id"])


def test_workflow_pack_run_catalog_route_supports_bounded_filters(
    client: TestClient,
) -> None:
    first_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-filter-001",
            caller_app="lotus-gateway",
            tenant_id="tenant-sg-001",
        ),
    )
    assert first_execute_response.status_code == 200
    second_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-filter-002",
            caller_app="lotus-gateway",
            tenant_id="tenant-us-002",
        ),
    )
    assert second_execute_response.status_code == 200

    all_runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    accepted_run_id = all_runs[0]["run_id"]
    awaiting_run_id = all_runs[1]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{accepted_run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.101",
            "reason": "Accepted for catalog filter coverage.",
        },
    )
    assert review_response.status_code == 200

    filtered_response = client.get(
        "/platform/workflow-packs/runs",
        params={
            "registration_ref": "advisor_brief.pack@v1",
            "caller_app": "lotus-gateway",
            "tenant_id": "tenant-sg-001",
            "workflow_surface": "advisor-brief-workspace",
            "runtime_state": "COMPLETED",
            "review_state": "AWAITING_REVIEW",
            "supportability_status": "ACTION_REQUIRED",
            "workflow_authority_owner": "lotus-gateway",
            "limit": 1,
        },
    )

    assert filtered_response.status_code == 200
    body = filtered_response.json()
    assert body["filters_applied"] == {
        "limit": 1,
        "registration_ref": "advisor_brief.pack@v1",
        "caller_app": "lotus-gateway",
        "tenant_id": "tenant-sg-001",
        "workflow_surface": "advisor-brief-workspace",
        "runtime_state": "COMPLETED",
        "review_state": "AWAITING_REVIEW",
        "supportability_status": "ACTION_REQUIRED",
        "workflow_authority_owner": "lotus-gateway",
    }
    assert body["run_count"] == 1
    assert body["ready_count"] == 0
    assert body["action_required_count"] == 1
    assert body["historical_count"] == 0
    assert [run["run_id"] for run in body["runs"]] == [awaiting_run_id]
    assert body["runs"][0]["caller_app"] == "lotus-gateway"
    assert body["runs"][0]["tenant_id"] == "tenant-sg-001"
    assert body["runs"][0]["workflow_surface"] == "advisor-brief-workspace"
    assert body["runs"][0]["supportability_status"] == "ACTION_REQUIRED"


def test_workflow_pack_execute_route_records_explicit_run_and_returns_run_id(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]
    assert body["workflow_pack_run"]["workflow_surface"] == "advisor-brief-workspace"
    _assert_task_flow_recorded_for_run(client=client, run_id=body["workflow_pack_run"]["run_id"])


def test_workflow_pack_execute_route_defaults_workflow_surface_from_binding(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-default-surface-001",
            workflow_surface=None,
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["workflow_pack_run"]["workflow_surface"] == "advisor-brief-workspace"


def test_workflow_pack_execute_route_records_workspace_rationale_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=workspace_rationale_workflow_pack_execution_request_json(
            correlation_id="corr-workspace-rationale-pack-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["workflow_pack_run"]["pack_id"] == "workspace_rationale.pack"
    assert body["workflow_pack_run"]["registration_ref"] == "workspace_rationale.pack@v1"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-advise"
    assert body["workflow_pack_run"]["workflow_surface"] == "advisory-workspace-assistant"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-advise"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]


def test_workflow_pack_execute_route_records_twr_inspection_support_brief_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=twr_inspection_support_brief_workflow_pack_execution_request_json(
            correlation_id="corr-twr-inspection-support-brief-pack-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["workflow_pack_run"]["pack_id"] == "twr_inspection_support_brief.pack"
    assert body["workflow_pack_run"]["registration_ref"] == "twr_inspection_support_brief.pack@v1"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-performance"
    assert body["workflow_pack_run"]["workflow_surface"] == "twr-supportability-inspection"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-performance"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]


def test_workflow_pack_execute_route_records_outcome_review_narrative_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=outcome_review_narrative_workflow_pack_execution_request_json(
            correlation_id="corr-outcome-review-narrative-pack-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    structured_output = body["execution"]["result"]["structured_output"]
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["workflow_pack_run"]["pack_id"] == "outcome_review_narrative.pack"
    assert body["workflow_pack_run"]["registration_ref"] == "outcome_review_narrative.pack@v1"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-manage"
    assert body["workflow_pack_run"]["workflow_surface"] == "dpm-outcome-review-ai-evidence"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-manage"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]
    assert structured_output["outcome_review_narrative_status"] == "REVIEW_REQUIRED"
    assert structured_output["unsupported_claims"] == [
        "client_contact",
        "trade_approval",
        "portfolio_manager_scoring",
        "source_fact_invention",
    ]
    assert "score_portfolio_manager" in structured_output["forbidden_actions_enforced"]
    _assert_task_flow_recorded_for_run(client=client, run_id=body["workflow_pack_run"]["run_id"])


def test_workflow_pack_source_events_project_ai_run_without_raw_payloads(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=outcome_review_narrative_workflow_pack_execution_request_json(
            correlation_id="corr-outcome-review-source-events-001",
            include_portfolio_memory_context=True,
        ),
    )
    assert execute_response.status_code == 200
    run_id = execute_response.json()["workflow_pack_run"]["run_id"]

    source_events_response = client.get(f"/platform/workflow-packs/runs/{run_id}/source-events")

    assert source_events_response.status_code == 200
    body = source_events_response.json()
    assert body["run_id"] == run_id
    assert body["event_count"] == 1
    assert body["no_raw_payloads"] is True
    assert "must not reconstruct portfolio-memory" in body["source_authority_policy"]
    source_event = body["events"][0]
    assert source_event["event_type"] == "AI_WORKFLOW_PACK_RUN_RECORDED"
    assert source_event["source_system"] == "lotus-ai"
    assert source_event["source_type"] == "AI_WORKFLOW_PACK_RUN"
    assert source_event["event_identity"].startswith(f"lotus-ai:AI_WORKFLOW_PACK_RUN:{run_id}:")
    assert source_event["content_hash"].startswith("sha256:")
    assert source_event["portfolio_id"] == "PB_SG_GLOBAL_BAL_001"
    assert source_event["pack_id"] == "outcome_review_narrative.pack"
    assert source_event["workflow_authority_owner"] == "lotus-manage"
    assert source_event["supportability_status"] == "ACTION_REQUIRED"
    assert source_event["portfolio_memory_status"] == "supplied"
    assert source_event["portfolio_memory_content_hash"] == "sha256:portfolio-memory-context-001"
    assert source_event["event_ref_count"] == 2
    assert source_event["retention_policy"] == "AI_WORKFLOW_PACK_SOURCE_EVENT_7Y"
    assert source_event["redaction_policy"] == "NO_RAW_PAYLOADS"
    assert source_event["audit_policy"] == "AUDIT_READ_AND_EXPORT"
    assert source_event["access_classification"] == "CLIENT_CONFIDENTIAL_INTERNAL"
    assert source_event["source_refs"] == [
        "lotus-manage:outcome-ai-evidence:or_pb_sg_001",
        "lotus-manage:outcome-review:or_pb_sg_001",
    ]
    assert source_event["artifact_refs"][0]["source_object_id"] == run_id
    assert source_event["evidence_descriptor_count"] >= 1

    response_text = source_events_response.text
    assert "Outcome review or_pb_sg_001 for portfolio" not in response_text
    assert '"raw_payload":' not in response_text
    assert "portfolio-memory-source-000" not in response_text


def test_workflow_pack_source_event_catalog_filters_and_reports_review_lineage(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=proof_pack_pm_memo_workflow_pack_execution_request_json(
            correlation_id="corr-proof-pack-source-events-001",
            include_portfolio_memory_context=True,
        ),
    )
    assert execute_response.status_code == 200
    run_id = execute_response.json()["workflow_pack_run"]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-manage",
            "reviewed_by": "pm.sg.source-events.001",
            "reason": "Accepted for source-event lineage proof.",
        },
    )
    assert review_response.status_code == 200

    catalog_response = client.get(
        "/platform/workflow-packs/source-events",
        params={
            "pack_id": "dpm_pm_memo.pack",
            "caller_app": "lotus-manage",
            "tenant_id": "tenant-sg-001",
            "workflow_surface": "dpm-proof-pack-ai-evidence",
            "supportability_status": "READY",
            "limit": 10,
        },
    )

    assert catalog_response.status_code == 200
    body = catalog_response.json()
    assert body["filters_applied"] == {
        "limit": 10,
        "pack_id": "dpm_pm_memo.pack",
        "caller_app": "lotus-manage",
        "tenant_id": "tenant-sg-001",
        "workflow_surface": "dpm-proof-pack-ai-evidence",
        "supportability_status": "READY",
    }
    assert body["event_count"] == 2
    assert body["ready_count"] == 2
    assert body["action_required_count"] == 0
    assert body["historical_count"] == 0
    assert body["no_raw_payloads"] is True
    assert {event["event_type"] for event in body["events"]} == {
        "AI_WORKFLOW_PACK_RUN_RECORDED",
        "AI_WORKFLOW_PACK_REVIEW_STATE_UPDATED",
    }
    assert {event["run_id"] for event in body["events"]} == {run_id}
    assert all(event["portfolio_id"] == "PB_SG_GLOBAL_BAL_001" for event in body["events"])
    assert all(event["redaction_policy"] == "NO_RAW_PAYLOADS" for event in body["events"])


def test_workflow_pack_run_source_events_reject_unknown_run(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/unknown-run/source-events")

    assert response.status_code == 404


def test_workflow_pack_execute_route_allows_gateway_outcome_review_narrative_handoff(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=outcome_review_narrative_workflow_pack_execution_request_json(
            correlation_id="corr-outcome-review-narrative-gateway-pack-001",
            caller_app="lotus-gateway",
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    structured_output = body["execution"]["result"]["structured_output"]
    assert body["eligibility"]["allowed"] is True
    assert body["workflow_pack_run"]["pack_id"] == "outcome_review_narrative.pack"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-gateway"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-manage"
    assert structured_output["outcome_review_narrative_status"] == "REVIEW_REQUIRED"
    assert structured_output["evidence_content_hash"] == "sha256:outcome-ai-evidence-001"
    assert "contact_client" in structured_output["forbidden_actions_enforced"]


def test_workflow_pack_execute_route_records_wave_pm_memo_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=wave_pm_memo_workflow_pack_execution_request_json(
            correlation_id="corr-wave-pm-memo-pack-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    structured_output = body["execution"]["result"]["structured_output"]
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["workflow_pack_run"]["pack_id"] == "dpm_wave_pm_memo.pack"
    assert body["workflow_pack_run"]["registration_ref"] == "dpm_wave_pm_memo.pack@v1"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-manage"
    assert body["workflow_pack_run"]["workflow_surface"] == "dpm-wave-ai-evidence"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-manage"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]
    assert structured_output["workflow_pack_family"] == "dpm_wave_pm_memo"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["wave_report_content_hash"] == "sha256:wave-report-input-001"
    assert structured_output["proof_pack_ref_count"] == 1
    _assert_task_flow_recorded_for_run(client=client, run_id=body["workflow_pack_run"]["run_id"])


def test_workflow_pack_execute_route_records_dpm_exception_summary_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=dpm_exception_summary_workflow_pack_execution_request_json(
            correlation_id="corr-dpm-exception-summary-pack-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    structured_output = body["execution"]["result"]["structured_output"]
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["workflow_pack_run"]["pack_id"] == "dpm_exception_summary.pack"
    assert body["workflow_pack_run"]["registration_ref"] == "dpm_exception_summary.pack@v1"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-manage"
    assert body["workflow_pack_run"]["workflow_surface"] == "dpm-exception-summary-ai-evidence"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-manage"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]
    assert structured_output["workflow_pack_family"] == "dpm_exception_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["exception_count"] == 2
    assert structured_output["open_exception_count"] == 2
    _assert_task_flow_recorded_for_run(client=client, run_id=body["workflow_pack_run"]["run_id"])


def test_workflow_pack_execute_route_blocks_dpm_exception_summary_forbidden_output(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute",
        json=dpm_exception_summary_workflow_pack_execution_request_json(
            correlation_id="corr-dpm-exception-summary-blocked-output-001",
            requested_outputs=["exception_summary", "portfolio_manager_score"],
        ),
    )

    assert response.status_code == 422
    body = response.json()
    assert "DPM_EXCEPTION_SUMMARY_GUARDRAIL_BLOCKED" in body["detail"]
    assert (
        "Forbidden exception summary outputs requested: portfolio_manager_score" in body["detail"]
    )


def test_workflow_pack_execute_route_records_pm_quality_summary_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=pm_quality_summary_workflow_pack_execution_request_json(
            correlation_id="corr-pm-quality-summary-pack-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    structured_output = body["execution"]["result"]["structured_output"]
    assert body["eligibility"]["allowed"] is True
    assert body["execution"]["status"] == "COMPLETED"
    assert body["workflow_pack_run"]["pack_id"] == "pm_quality_summary.pack"
    assert body["workflow_pack_run"]["registration_ref"] == "pm_quality_summary.pack@v1"
    assert body["workflow_pack_run"]["caller_app"] == "lotus-manage"
    assert body["workflow_pack_run"]["workflow_surface"] == "dpm-pm-quality-ai-evidence"
    assert body["workflow_pack_run"]["workflow_authority_owner"] == "lotus-manage"
    assert body["execution"]["audit"]["workflow_pack_run_id"] == body["workflow_pack_run"]["run_id"]
    assert structured_output["workflow_pack_family"] == "pm_quality_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["score_run_content_hash"] == "sha256:pm-quality-score-run-001"
    assert structured_output["indicator_result_count"] == 1
    _assert_task_flow_recorded_for_run(client=client, run_id=body["workflow_pack_run"]["run_id"])


def test_workflow_pack_execute_route_blocks_pm_quality_summary_pm_ranking(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute",
        json=pm_quality_summary_workflow_pack_execution_request_json(
            correlation_id="corr-pm-quality-summary-blocked-ranking-001",
            requested_outputs=["score_run_summary", "pm_ranking"],
        ),
    )

    assert response.status_code == 422
    body = response.json()
    assert "PM_QUALITY_SUMMARY_GUARDRAIL_BLOCKED" in body["detail"]
    assert "Forbidden PM quality summary outputs requested: pm_ranking" in body["detail"]


def test_workflow_pack_execute_route_blocks_wave_pm_memo_execution_claim(
    client: TestClient,
) -> None:
    request = wave_pm_memo_workflow_pack_execution_request_json(
        correlation_id="corr-wave-pm-memo-blocked-execution-001"
    )
    task_request = cast(dict[str, Any], request["task_request"])
    context = cast(dict[str, Any], task_request["context"])
    payload = cast(dict[str, Any], context["payload"])
    wave_report_input = cast(dict[str, Any], payload["wave_report_input"])
    wave_report_input["external_execution_claimed"] = True

    response = client.post("/platform/workflow-packs/execute", json=request)

    assert response.status_code == 422
    body = response.json()
    assert "WAVE_PM_MEMO_GUARDRAIL_BLOCKED" in body["detail"]
    assert "cannot claim external execution authority" in body["detail"]


def test_workflow_pack_execute_route_blocks_outcome_review_narrative_forbidden_output(
    client: TestClient,
) -> None:
    response = client.post(
        "/platform/workflow-packs/execute",
        json=outcome_review_narrative_workflow_pack_execution_request_json(
            correlation_id="corr-outcome-review-narrative-blocked-output-001",
            requested_outputs=["pm_summary", "pm_score"],
        ),
    )

    assert response.status_code == 422
    body = response.json()
    assert "OUTCOME_REVIEW_NARRATIVE_GUARDRAIL_BLOCKED" in body["detail"]
    assert "Forbidden narrative outputs requested: pm_score" in body["detail"]


def test_workflow_pack_execute_route_blocks_outcome_review_narrative_forbidden_field(
    client: TestClient,
) -> None:
    request = outcome_review_narrative_workflow_pack_execution_request_json(
        correlation_id="corr-outcome-review-narrative-blocked-field-001"
    )
    task_request = cast(dict[str, Any], request["task_request"])
    context = cast(dict[str, Any], task_request["context"])
    payload = cast(dict[str, Any], context["payload"])
    ai_evidence_input = cast(dict[str, Any], payload["ai_evidence_input"])
    ai_evidence_input["raw_payload"] = {"unsafe": True}

    response = client.post("/platform/workflow-packs/execute", json=request)

    assert response.status_code == 422
    body = response.json()
    assert "OUTCOME_REVIEW_NARRATIVE_GUARDRAIL_BLOCKED" in body["detail"]
    assert "Forbidden AI evidence fields present: raw_payload" in body["detail"]


def test_workflow_pack_execute_route_records_failed_run_when_runtime_execution_is_unavailable(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_execution.resolve_task_execution",
        lambda **_: (_ for _ in ()).throw(
            HTTPException(
                status_code=503,
                detail=(
                    "LIVE_EXECUTION_NOT_ENABLED: Local OpenAI-compatible endpoint is not "
                    "reachable from lotus-ai."
                ),
            )
        ),
    )

    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-failed-001"
        ),
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    run_id = body["workflow_pack_run"]["run_id"]
    assert body["execution"]["status"] == "FAILED"
    assert body["execution"]["result"]["message"].startswith("LIVE_EXECUTION_NOT_ENABLED:")
    assert body["execution"]["audit"]["workflow_pack_run_id"] == run_id
    assert body["workflow_pack_run"]["runtime_state"] == "FAILED"
    assert body["workflow_pack_run"]["allowed_review_actions"] == []
    assert body["workflow_pack_run"]["supportability_status"] == "ACTION_REQUIRED"
    _assert_task_flow_recorded_for_run(
        client=client,
        run_id=run_id,
        expected_status="FAILED",
    )

    consumer_response = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view")
    assert consumer_response.status_code == 200
    consumer_body = consumer_response.json()
    assert consumer_body["runtime"]["state"] == "FAILED"
    assert consumer_body["supportability"]["status"] == "ACTION_REQUIRED"
    assert consumer_body["supportability"]["partial_output_visible"] is True

    operator_response = client.get(f"/platform/workflow-packs/runs/{run_id}/operator-profile")
    assert operator_response.status_code == 200
    operator_body = operator_response.json()
    assert operator_body["runtime_state"] == "FAILED"
    assert operator_body["supportability_status"] == "ACTION_REQUIRED"
    assert any(finding["finding_id"] == "runtime_failed" for finding in operator_body["findings"])

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.failed",
            "reason": "Failed runtime output must not be accepted as workflow truth.",
        },
    )
    assert review_response.status_code == 409
    assert "runtime state `FAILED`" in review_response.json()["detail"]

    unchanged_detail_response = client.get(f"/platform/workflow-packs/runs/{run_id}")
    assert unchanged_detail_response.status_code == 200
    unchanged_detail = unchanged_detail_response.json()
    assert unchanged_detail["run"]["review_state"] == "AWAITING_REVIEW"
    assert unchanged_detail["review"]["review_transition_count"] == 0
    assert [event["event_type"] for event in unchanged_detail["events"]] == ["RUN_RECORDED"]


def test_workflow_pack_execute_route_rejects_wrong_task_for_binding(client: TestClient) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-wrong-task-001",
            task_id="summarize.v1",
        ),
    )

    assert execute_response.status_code == 409


def test_workflow_pack_execute_route_rejects_denied_surface(client: TestClient) -> None:
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-denied-001",
            workflow_surface="unsupported-surface",
        ),
    )

    assert execute_response.status_code == 403


def test_workflow_pack_execute_route_rejects_full_queue_lane_without_side_effects(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    first_lease = acquire_workflow_pack_queue_admission(registration=registration)
    second_lease = acquire_workflow_pack_queue_admission(registration=registration)

    try:
        baseline_audit_response = client.get(
            "/ai/audit",
            params={"caller_app": "lotus-gateway", "limit": 10},
        )
        execute_response = client.post(
            "/platform/workflow-packs/execute",
            json=advisor_brief_workflow_pack_execution_request_json(
                correlation_id="corr-pack-execute-queue-full-001"
            ),
        )
        audit_response = client.get(
            "/ai/audit",
            params={"caller_app": "lotus-gateway", "limit": 10},
        )
        run_catalog_response = client.get("/platform/workflow-packs/runs")
    finally:
        release_workflow_pack_queue_admission(first_lease.queue_item_id)
        release_workflow_pack_queue_admission(second_lease.queue_item_id)

    assert baseline_audit_response.status_code == 200
    assert execute_response.status_code == 429
    assert "Workflow-pack queue policy rejected admission" in execute_response.json()["detail"]
    assert "max_concurrent_runs_per_lane" in execute_response.json()["detail"]
    assert audit_response.status_code == 200
    assert audit_response.json()["records"] == baseline_audit_response.json()["records"]
    assert run_catalog_response.status_code == 200
    assert run_catalog_response.json()["run_count"] == 0


def test_workflow_pack_execute_route_uses_requested_allowed_queue_lane(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    first_latency_lease = acquire_workflow_pack_queue_admission(registration=registration)
    second_latency_lease = acquire_workflow_pack_queue_admission(registration=registration)

    try:
        execute_response = client.post(
            "/platform/workflow-packs/execute",
            json=advisor_brief_workflow_pack_execution_request_json(
                correlation_id="corr-pack-execute-review-lane-001",
                queue_lane="REVIEW_SUPPORT",
            ),
        )
        run_catalog_response = client.get("/platform/workflow-packs/runs")
    finally:
        release_workflow_pack_queue_admission(first_latency_lease.queue_item_id)
        release_workflow_pack_queue_admission(second_latency_lease.queue_item_id)

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["workflow_pack_run"]["correlation_id"] == ("corr-pack-execute-review-lane-001")
    assert run_catalog_response.status_code == 200
    assert run_catalog_response.json()["run_count"] == 1


def test_workflow_pack_execute_route_rejects_unsupported_queue_lane_without_side_effects(
    client: TestClient,
) -> None:
    baseline_audit_response = client.get(
        "/ai/audit",
        params={"caller_app": "lotus-gateway", "limit": 10},
    )
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=advisor_brief_workflow_pack_execution_request_json(
            correlation_id="corr-pack-execute-unsupported-lane-001",
            queue_lane="NIGHTLY",
        ),
    )
    audit_response = client.get(
        "/ai/audit",
        params={"caller_app": "lotus-gateway", "limit": 10},
    )
    run_catalog_response = client.get("/platform/workflow-packs/runs")

    assert baseline_audit_response.status_code == 200
    assert execute_response.status_code == 409
    assert "not allowed" in execute_response.json()["detail"]
    assert audit_response.status_code == 200
    assert audit_response.json()["records"] == baseline_audit_response.json()["records"]
    assert run_catalog_response.status_code == 200
    assert run_catalog_response.json()["run_count"] == 0


def test_pack_backed_task_route_rejects_full_queue_lane_without_side_effects(
    client: TestClient,
) -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    first_lease = acquire_workflow_pack_queue_admission(registration=registration)
    second_lease = acquire_workflow_pack_queue_admission(registration=registration)

    try:
        baseline_audit_response = client.get(
            "/ai/audit",
            params={"caller_app": "lotus-gateway", "limit": 10},
        )
        task_response = client.post(
            "/ai/tasks/execute",
            json=advisor_brief_task_execution_request_json(
                correlation_id="corr-pack-task-queue-full-001"
            ),
        )
        audit_response = client.get(
            "/ai/audit",
            params={"caller_app": "lotus-gateway", "limit": 10},
        )
        run_catalog_response = client.get("/platform/workflow-packs/runs")
    finally:
        release_workflow_pack_queue_admission(first_lease.queue_item_id)
        release_workflow_pack_queue_admission(second_lease.queue_item_id)

    assert baseline_audit_response.status_code == 200
    assert task_response.status_code == 429
    assert "Workflow-pack queue policy rejected admission" in task_response.json()["detail"]
    assert "max_concurrent_runs_per_lane" in task_response.json()["detail"]
    assert audit_response.status_code == 200
    assert audit_response.json()["records"] == baseline_audit_response.json()["records"]
    assert run_catalog_response.status_code == 200
    assert run_catalog_response.json()["run_count"] == 0


def test_workflow_pack_execute_route_degrades_when_registry_store_is_unmigrated(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-execute-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_registry_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            execute_response = durable_client.post(
                "/platform/workflow-packs/execute",
                json=advisor_brief_workflow_pack_execution_request_json(
                    correlation_id="corr-pack-execute-unmigrated-001"
                ),
            )

    assert execute_response.status_code == 503
    assert "Workflow-pack registry store is not ready." in execute_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in execute_response.json()["detail"]


def test_workflow_pack_run_routes_degrade_when_sql_run_store_is_unmigrated(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            catalog_response = durable_client.get("/platform/workflow-packs/runs")
            detail_response = durable_client.get("/platform/workflow-packs/runs/packrun_missing")
            consumer_response = durable_client.get(
                "/platform/workflow-packs/runs/packrun_missing/consumer-view"
            )
            operator_response = durable_client.get(
                "/platform/workflow-packs/runs/packrun_missing/operator-profile"
            )
            review_response = durable_client.post(
                "/platform/workflow-packs/runs/packrun_missing/review-actions",
                json={
                    "action_type": "ACCEPT",
                    "caller_app": "lotus-gateway",
                    "reviewed_by": "banker.sg.degraded",
                    "reason": "Run-store readiness should degrade before missing-run handling.",
                },
            )

    for response in (
        catalog_response,
        detail_response,
        consumer_response,
        operator_response,
        review_response,
    ):
        assert response.status_code == 503
        assert "Workflow-pack run store is not ready." in response.json()["detail"]
        assert "MIGRATION_REQUIRED" in response.json()["detail"]


def test_pack_backed_execution_routes_degrade_when_sql_run_store_is_unmigrated(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-execution-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            baseline_audit_response = durable_client.get(
                "/ai/audit",
                params={"caller_app": "lotus-gateway", "limit": 10},
            )
            task_response = durable_client.post(
                "/ai/tasks/execute",
                json=advisor_brief_task_execution_request_json(
                    correlation_id="corr-pack-run-unmigrated-task-001"
                ),
            )
            explicit_response = durable_client.post(
                "/platform/workflow-packs/execute",
                json=advisor_brief_workflow_pack_execution_request_json(
                    correlation_id="corr-pack-run-unmigrated-explicit-001"
                ),
            )
            audit_response = durable_client.get(
                "/ai/audit",
                params={"caller_app": "lotus-gateway", "limit": 10},
            )

    assert task_response.status_code == 503
    assert "Workflow-pack run store is not ready." in task_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in task_response.json()["detail"]

    assert explicit_response.status_code == 503
    assert "Workflow-pack run store is not ready." in explicit_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in explicit_response.json()["detail"]
    assert baseline_audit_response.status_code == 200
    assert audit_response.status_code == 200
    assert audit_response.json()["record_count"] == baseline_audit_response.json()["record_count"]


def test_pack_backed_execution_routes_degrade_when_sql_task_flow_store_is_unmigrated(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-execution-unmigrated.db'}"

    with override_runtime_settings(
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            baseline_audit_response = durable_client.get(
                "/ai/audit",
                params={"caller_app": "lotus-gateway", "limit": 10},
            )
            task_response = durable_client.post(
                "/ai/tasks/execute",
                json=advisor_brief_task_execution_request_json(
                    correlation_id="corr-pack-task-flow-unmigrated-task-001"
                ),
            )
            explicit_response = durable_client.post(
                "/platform/workflow-packs/execute",
                json=advisor_brief_workflow_pack_execution_request_json(
                    correlation_id="corr-pack-task-flow-unmigrated-explicit-001"
                ),
            )
            audit_response = durable_client.get(
                "/ai/audit",
                params={"caller_app": "lotus-gateway", "limit": 10},
            )

    assert task_response.status_code == 503
    assert "Workflow-pack task-flow store is not ready." in task_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in task_response.json()["detail"]

    assert explicit_response.status_code == 503
    assert "Workflow-pack task-flow store is not ready." in explicit_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in explicit_response.json()["detail"]
    assert baseline_audit_response.status_code == 200
    assert audit_response.status_code == 200
    assert audit_response.json()["record_count"] == baseline_audit_response.json()["record_count"]


def test_workflow_pack_run_detail_rejects_unknown_run(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/unknown-run")

    assert response.status_code == 404


def test_workflow_pack_run_review_action_updates_review_state(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-review-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.100",
            "reason": "Advisor brief accepted for bounded downstream workflow use.",
        },
    )

    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["run"]["review_state"] == "ACCEPTED"
    assert review_body["run"]["allowed_review_actions"] == ["SUPERSEDE"]
    assert review_body["events"][0]["event_type"] == "REVIEW_STATE_UPDATED"
    catalog_response = client.get("/platform/workflow-packs/runs")
    assert catalog_response.status_code == 200
    catalog_run = catalog_response.json()["runs"][0]
    assert catalog_run["review_summary"]["latest_review_event_at"] is not None
    assert catalog_run["review_summary"]["latest_review_actor"] == "review:banker.sg.100"
    assert catalog_run["review_summary"]["review_transition_count"] == 1
    assert catalog_run["review_summary"]["has_review_history"] is True
    detail_response = client.get(f"/platform/workflow-packs/runs/{run_id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["review_state"] == "ACCEPTED"
    assert detail_body["review"]["state"] == "ACCEPTED"
    assert detail_body["provenance"]["artifact_ref_count"] == 1
    assert "task_contract" in detail_body["provenance"]["evidence_types"]
    assert detail_body["review"]["latest_review_event_at"] is not None
    assert detail_body["review"]["latest_review_actor"] == "review:banker.sg.100"
    assert detail_body["review"]["review_transition_count"] == 1
    assert detail_body["review"]["has_review_history"] is True

    task_flow_response = client.get("/platform/workflow-packs/task-flows")
    assert task_flow_response.status_code == 200
    task_flow = task_flow_response.json()["task_flows"][0]
    assert task_flow["flow_status"] == "COMPLETED"
    assert task_flow["review_states"][run_id] == "ACCEPTED"
    assert task_flow["supportability_status"] == "READY"
    assert task_flow["handoff_refs"] == [
        {
            "handoff_id": f"{task_flow['task_flow_id']}_handoff_{run_id}",
            "owner_service": "lotus-gateway",
            "status": "READY_FOR_HANDOFF",
            "domain_ref": None,
            "evidence_refs": [
                {
                    "evidence_type": "workflow_pack_review_handoff_ready",
                    "summary": (
                        "Accepted workflow-pack task flow is ready for domain-owner handoff."
                    ),
                    "attributes": {
                        "run_id": run_id,
                        "task_flow_id": task_flow["task_flow_id"],
                        "workflow_authority_owner": "lotus-gateway",
                        "reason": "Advisor brief accepted for bounded downstream workflow use.",
                    },
                }
            ],
        }
    ]


def test_workflow_pack_run_review_action_allows_operator_caller(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-review-operator-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-platform",
            "reviewed_by": "ops.sg.platform.001",
            "reason": "Platform operator recorded bounded review acceptance.",
        },
    )

    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["run"]["review_state"] == "ACCEPTED"
    assert review_body["run"]["allowed_review_actions"] == ["SUPERSEDE"]
    assert review_body["events"][0]["event_type"] == "REVIEW_STATE_UPDATED"
    assert review_body["events"][0]["actor"] == "review:ops.sg.platform.001"

    catalog_response = client.get("/platform/workflow-packs/runs")
    assert catalog_response.status_code == 200
    catalog_run = catalog_response.json()["runs"][0]
    assert catalog_run["review_summary"]["latest_review_actor"] == "review:ops.sg.platform.001"
    assert catalog_run["review_summary"]["review_transition_count"] == 1


def test_workflow_pack_run_review_action_rejects_unbounded_caller(client: TestClient) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-review-forbidden-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-manage",
            "reviewed_by": "banker.sg.forbidden.001",
            "reason": "Cross-app review caller should remain blocked.",
        },
    )

    assert review_response.status_code == 403
    assert (
        review_response.json()["detail"]
        == "Workflow-pack review-state actions are currently limited to the original active registered caller app or a caller authorized for async control-plane actions while downstream review integration remains bounded."
    )

    detail_response = client.get(f"/platform/workflow-packs/runs/{run_id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["run"]["review_state"] == "AWAITING_REVIEW"
    assert detail_body["review"]["review_transition_count"] == 0
    assert len(detail_body["events"]) == 1
    assert detail_body["events"][0]["event_type"] == "RUN_RECORDED"


def test_workflow_pack_run_review_action_revise_links_replacement_lineage(
    client: TestClient,
) -> None:
    original_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-001"
        ),
    )
    assert original_execute_response.status_code == 200

    revised_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-002",
            summary="Draft revised advisor brief from source performance facts.",
            portfolio_return_pct=1.55,
            active_return_pct=-6.38,
        ),
    )
    assert revised_execute_response.status_code == 200

    runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    original_run_id = next(
        run["run_id"] for run in runs if run["correlation_id"] == "corr-pack-run-api-revise-001"
    )
    revised_run_id = next(
        run["run_id"] for run in runs if run["correlation_id"] == "corr-pack-run-api-revise-002"
    )

    review_response = client.post(
        f"/platform/workflow-packs/runs/{original_run_id}/review-actions",
        json={
            "action_type": "REVISE",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.revise.001",
            "reason": "Reviewer requested a revised advisor brief draft.",
            "replacement_run_id": revised_run_id,
        },
    )

    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["run"]["review_state"] == "REVISED"
    assert review_body["run"]["superseded_by_run_id"] == revised_run_id
    assert review_body["run"]["replacement_run_id"] == revised_run_id
    assert review_body["run"]["allowed_review_actions"] == []
    assert any(event["event_type"] == "LINEAGE_UPDATED" for event in review_body["events"])
    assert any(
        f"Replacement lineage now points to `{revised_run_id}`" in line
        for line in review_body["summary"]
    )

    replacement_detail_response = client.get(f"/platform/workflow-packs/runs/{revised_run_id}")
    assert replacement_detail_response.status_code == 200
    replacement_detail_body = replacement_detail_response.json()
    assert replacement_detail_body["run"]["supersedes_run_id"] == original_run_id
    assert any(
        event["event_type"] == "LINEAGE_UPDATED" for event in replacement_detail_body["events"]
    )

    task_flow_response = client.get("/platform/workflow-packs/task-flows")
    assert task_flow_response.status_code == 200
    task_flows = task_flow_response.json()["task_flows"]
    original_task_flow = next(flow for flow in task_flows if original_run_id in flow["run_refs"])
    revised_task_flow = next(flow for flow in task_flows if revised_run_id in flow["run_refs"])
    expected_lineage = {
        "superseded_run_id": original_run_id,
        "replacement_run_id": revised_run_id,
        "review_action_ref": "REVISE",
        "reason": "Reviewer requested a revised advisor brief draft.",
    }
    assert original_task_flow["flow_status"] == "SUPERSEDED"
    assert original_task_flow["review_states"][original_run_id] == "REVISED"
    assert original_task_flow["supportability_status"] == "HISTORICAL"
    assert expected_lineage in original_task_flow["replacement_lineage"]
    assert expected_lineage in revised_task_flow["replacement_lineage"]


def test_workflow_pack_run_review_action_rejects_unknown_replacement_run(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-missing-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "REVISE",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.revise.missing.001",
            "reason": "Unknown replacement run id should fail through the API contract.",
            "replacement_run_id": "packrun_advisor_brief_pack_missing",
        },
    )

    assert review_response.status_code == 404
    assert (
        review_response.json()["detail"]
        == "Unknown replacement workflow-pack run: packrun_advisor_brief_pack_missing"
    )


def test_workflow_pack_run_review_action_rejects_cross_family_replacement_lineage(
    client: TestClient,
) -> None:
    original_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-cross-family-001"
        ),
    )
    assert original_execute_response.status_code == 200

    replacement_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-cross-family-002"
        ),
    )
    assert replacement_execute_response.status_code == 200

    runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    original_run_id = next(
        run["run_id"]
        for run in runs
        if run["correlation_id"] == "corr-pack-run-api-revise-cross-family-001"
    )
    replacement_run_id = next(
        run["run_id"]
        for run in runs
        if run["correlation_id"] == "corr-pack-run-api-revise-cross-family-002"
    )

    store = get_workflow_pack_run_store()
    replacement_record = store.get_run(run_id=replacement_run_id)
    assert replacement_record is not None
    store.save_run(replace(replacement_record, pack_family="different_family"))

    review_response = client.post(
        f"/platform/workflow-packs/runs/{original_run_id}/review-actions",
        json={
            "action_type": "REVISE",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.revise.cross-family.001",
            "reason": "Cross-family lineage should remain blocked.",
            "replacement_run_id": replacement_run_id,
        },
    )

    assert review_response.status_code == 409
    assert (
        review_response.json()["detail"]
        == "Replacement workflow-pack run must belong to the same pack family to preserve bounded review-state lineage."
    )


def test_workflow_pack_run_review_action_rejects_cross_workflow_replacement_lineage(
    client: TestClient,
) -> None:
    original_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-cross-workflow-001"
        ),
    )
    assert original_execute_response.status_code == 200

    replacement_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-cross-workflow-002"
        ),
    )
    assert replacement_execute_response.status_code == 200

    runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    original_run_id = next(
        run["run_id"]
        for run in runs
        if run["correlation_id"] == "corr-pack-run-api-revise-cross-workflow-001"
    )
    replacement_run_id = next(
        run["run_id"]
        for run in runs
        if run["correlation_id"] == "corr-pack-run-api-revise-cross-workflow-002"
    )

    store = get_workflow_pack_run_store()
    replacement_record = store.get_run(run_id=replacement_run_id)
    assert replacement_record is not None
    store.save_run(replace(replacement_record, workflow_authority_owner="lotus-manage"))

    review_response = client.post(
        f"/platform/workflow-packs/runs/{original_run_id}/review-actions",
        json={
            "action_type": "REVISE",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.revise.cross-workflow.001",
            "reason": "Cross-workflow lineage should remain blocked.",
            "replacement_run_id": replacement_run_id,
        },
    )

    assert review_response.status_code == 409
    assert (
        review_response.json()["detail"]
        == "Replacement workflow-pack run must preserve workflow authority owner, caller app, tenant scope, and workflow surface to keep review-state lineage inside one bounded downstream workflow."
    )


def test_workflow_pack_run_review_action_rejects_already_linked_replacement_lineage(
    client: TestClient,
) -> None:
    original_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-linked-001"
        ),
    )
    assert original_execute_response.status_code == 200

    replacement_execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-revise-linked-002"
        ),
    )
    assert replacement_execute_response.status_code == 200

    runs = client.get("/platform/workflow-packs/runs").json()["runs"]
    original_run_id = next(
        run["run_id"]
        for run in runs
        if run["correlation_id"] == "corr-pack-run-api-revise-linked-001"
    )
    replacement_run_id = next(
        run["run_id"]
        for run in runs
        if run["correlation_id"] == "corr-pack-run-api-revise-linked-002"
    )

    store = get_workflow_pack_run_store()
    replacement_record = store.get_run(run_id=replacement_run_id)
    assert replacement_record is not None
    store.save_run(
        replace(
            replacement_record,
            supersedes_run_id="packrun_advisor_brief_pack_already_linked",
        )
    )

    review_response = client.post(
        f"/platform/workflow-packs/runs/{original_run_id}/review-actions",
        json={
            "action_type": "REVISE",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.revise.linked.001",
            "reason": "Replacement lineage already linked elsewhere should remain blocked.",
            "replacement_run_id": replacement_run_id,
        },
    )

    assert review_response.status_code == 409
    assert (
        review_response.json()["detail"]
        == f"Replacement workflow-pack run `{replacement_run_id}` is already linked to `packrun_advisor_brief_pack_already_linked`."
    )


def test_workflow_pack_run_consumer_view_groups_runtime_review_and_lineage(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-consumer-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    consumer_view_response = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view")

    assert consumer_view_response.status_code == 200
    body = consumer_view_response.json()
    assert body["runtime"]["state"] == "COMPLETED"
    assert body["review"]["state"] == "AWAITING_REVIEW"
    assert body["review"]["allowed_actions"] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert body["review"]["latest_review_event_at"] is None
    assert body["review"]["latest_review_actor"] is None
    assert body["review"]["review_transition_count"] == 0
    assert body["review"]["has_review_history"] is False
    assert body["provenance_summary"]["artifact_ref_count"] == 1
    assert body["provenance_summary"]["artifact_types"] == ["run_output_summary"]
    assert body["provenance_summary"]["evidence_descriptor_count"] >= 1
    assert "task_contract" in body["provenance_summary"]["evidence_types"]
    assert body["supportability"]["status"] == "ACTION_REQUIRED"
    assert body["supportability"]["review_pending"] is True
    assert body["supportability"]["superseded"] is False
    assert body["supportability"]["partial_output_visible"] is False
    assert body["lineage"]["workflow_authority_owner"] == "lotus-gateway"
    assert "advisor_brief_status" in body["provenance"]["structured_output_keys"]
    assert len(body["provenance"]["artifact_refs"]) == 1
    assert body["provenance"]["artifact_refs"][0]["domain"] == "workflow_pack"


def test_workflow_pack_run_consumer_view_exposes_latest_review_transition(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-consumer-002"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.consumer.002",
            "reason": "Accepted for consumer view review metadata coverage.",
        },
    )
    assert review_response.status_code == 200

    consumer_view_response = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view")

    assert consumer_view_response.status_code == 200
    body = consumer_view_response.json()
    assert body["review"]["state"] == "ACCEPTED"
    assert body["review"]["latest_review_event_at"] is not None
    assert body["review"]["latest_review_actor"] == "review:banker.sg.consumer.002"
    assert body["review"]["review_transition_count"] == 1
    assert body["review"]["has_review_history"] is True
    assert body["provenance_summary"]["artifact_ref_count"] == 1
    assert "task_contract" in body["provenance_summary"]["evidence_types"]


def test_workflow_pack_run_operator_profile_reports_supportability_posture(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-operator-001"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    profile_response = client.get(f"/platform/workflow-packs/runs/{run_id}/operator-profile")

    assert profile_response.status_code == 200
    body = profile_response.json()
    assert body["run_id"] == run_id
    assert body["supportability_status"] == "ACTION_REQUIRED"
    assert body["review_pending"] is True
    assert body["provenance"]["artifact_ref_count"] == 1
    assert body["provenance"]["artifact_types"] == ["run_output_summary"]
    assert body["provenance"]["evidence_descriptor_count"] >= 1
    assert "task_contract" in body["provenance"]["evidence_types"]
    assert body["artifact_ref_count"] == 1
    assert body["latest_event_type"] == "RUN_RECORDED"
    assert body["latest_event_actor"] == "lotus-ai.workflow-pack-run-ledger"
    assert body["latest_review_event_at"] is None
    assert body["latest_review_actor"] is None
    assert body["review_transition_count"] == 0
    assert body["event_type_counts"] == {"RUN_RECORDED": 1}
    assert any(finding["finding_id"] == "review_pending" for finding in body["findings"])


def test_workflow_pack_run_operator_profile_exposes_latest_review_transition(
    client: TestClient,
) -> None:
    execute_response = client.post(
        "/ai/tasks/execute",
        json=advisor_brief_task_execution_request_json(
            correlation_id="corr-pack-run-api-operator-002"
        ),
    )
    assert execute_response.status_code == 200
    run_id = client.get("/platform/workflow-packs/runs").json()["runs"][0]["run_id"]

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-gateway",
            "reviewed_by": "banker.sg.operator.003",
            "reason": "Accepted for operator profile review metadata coverage.",
        },
    )
    assert review_response.status_code == 200

    profile_response = client.get(f"/platform/workflow-packs/runs/{run_id}/operator-profile")

    assert profile_response.status_code == 200
    body = profile_response.json()
    assert body["latest_event_type"] == "REVIEW_STATE_UPDATED"
    assert body["latest_review_event_at"] is not None
    assert body["latest_review_actor"] == "review:banker.sg.operator.003"
    assert body["review_transition_count"] == 1
    assert body["provenance"]["artifact_ref_count"] == 1
    assert "task_contract" in body["provenance"]["evidence_types"]


def test_workflow_pack_run_operator_profile_rejects_unknown_run(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/runs/unknown-run/operator-profile")

    assert response.status_code == 404


def test_workflow_pack_run_catalog_supports_sqlalchemy_store_mode(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-api.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as client:
            execute_response = client.post(
                "/ai/tasks/execute",
                json=advisor_brief_task_execution_request_json(
                    correlation_id="corr-pack-run-api-sql-001"
                ),
            )
            assert execute_response.status_code == 200

            catalog_response = client.get("/platform/workflow-packs/runs")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["run_store_mode"] == "sqlalchemy"
    assert catalog_body["run_count"] == 1
    assert len(catalog_body["runs"][0]["artifact_refs"]) == 1
    assert catalog_body["runs"][0]["artifact_refs"][0]["domain"] == "workflow_pack"


def test_sqlalchemy_workflow_pack_run_review_and_lineage_survive_restart(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-review-persistence.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        workflow_pack_run_store_mode="sqlalchemy",
        workflow_pack_task_flow_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as client:
            original_execute_response = client.post(
                "/ai/tasks/execute",
                json=advisor_brief_task_execution_request_json(
                    correlation_id="corr-pack-run-api-sql-revise-001"
                ),
            )
            assert original_execute_response.status_code == 200

            revised_execute_response = client.post(
                "/ai/tasks/execute",
                json=advisor_brief_task_execution_request_json(
                    correlation_id="corr-pack-run-api-sql-revise-002",
                    summary="Draft revised advisor brief from source performance facts.",
                    portfolio_return_pct=1.55,
                    active_return_pct=-6.38,
                ),
            )
            assert revised_execute_response.status_code == 200

            runs = client.get("/platform/workflow-packs/runs").json()["runs"]
            original_run_id = next(
                run["run_id"]
                for run in runs
                if run["correlation_id"] == "corr-pack-run-api-sql-revise-001"
            )
            revised_run_id = next(
                run["run_id"]
                for run in runs
                if run["correlation_id"] == "corr-pack-run-api-sql-revise-002"
            )

            review_response = client.post(
                f"/platform/workflow-packs/runs/{original_run_id}/review-actions",
                json={
                    "action_type": "REVISE",
                    "caller_app": "lotus-gateway",
                    "reviewed_by": "banker.sg.sql.001",
                    "reason": "Durable SQL-backed lineage and review-state proof.",
                    "replacement_run_id": revised_run_id,
                },
            )
            assert review_response.status_code == 200

        with TestClient(app) as restarted_client:
            catalog_response = restarted_client.get("/platform/workflow-packs/runs")
            original_detail_response = restarted_client.get(
                f"/platform/workflow-packs/runs/{original_run_id}"
            )
            revised_detail_response = restarted_client.get(
                f"/platform/workflow-packs/runs/{revised_run_id}"
            )
            revised_consumer_view_response = restarted_client.get(
                f"/platform/workflow-packs/runs/{revised_run_id}/consumer-view"
            )
            original_operator_profile_response = restarted_client.get(
                f"/platform/workflow-packs/runs/{original_run_id}/operator-profile"
            )
            runtime_status_response = restarted_client.get("/platform/runtime-status")
            task_flow_catalog_response = restarted_client.get("/platform/workflow-packs/task-flows")

    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["run_store_mode"] == "sqlalchemy"
    assert catalog_body["run_count"] == 2
    original_catalog_run = next(
        run for run in catalog_body["runs"] if run["run_id"] == original_run_id
    )
    revised_catalog_run = next(
        run for run in catalog_body["runs"] if run["run_id"] == revised_run_id
    )
    assert original_catalog_run["review_state"] == "REVISED"
    assert original_catalog_run["supportability_status"] == "HISTORICAL"
    assert original_catalog_run["superseded_by_run_id"] == revised_run_id
    assert (
        original_catalog_run["review_summary"]["latest_review_actor"] == "review:banker.sg.sql.001"
    )
    assert original_catalog_run["review_summary"]["review_transition_count"] == 1
    assert revised_catalog_run["review_state"] == "AWAITING_REVIEW"
    assert revised_catalog_run["supportability_status"] == "ACTION_REQUIRED"
    assert revised_catalog_run["supersedes_run_id"] == original_run_id

    assert original_detail_response.status_code == 200
    original_detail_body = original_detail_response.json()
    assert original_detail_body["run"]["review_state"] == "REVISED"
    assert original_detail_body["run"]["superseded_by_run_id"] == revised_run_id
    assert original_detail_body["review"]["latest_review_actor"] == "review:banker.sg.sql.001"
    assert original_detail_body["review"]["review_transition_count"] == 1
    assert any(event["event_type"] == "LINEAGE_UPDATED" for event in original_detail_body["events"])

    assert revised_detail_response.status_code == 200
    revised_detail_body = revised_detail_response.json()
    assert revised_detail_body["run"]["supersedes_run_id"] == original_run_id
    assert any(event["event_type"] == "LINEAGE_UPDATED" for event in revised_detail_body["events"])

    assert revised_consumer_view_response.status_code == 200
    revised_consumer_view_body = revised_consumer_view_response.json()
    assert revised_consumer_view_body["review"]["state"] == "AWAITING_REVIEW"
    assert revised_consumer_view_body["review"]["review_transition_count"] == 0
    assert revised_consumer_view_body["lineage"]["supersedes_run_id"] == original_run_id
    assert revised_consumer_view_body["supportability"]["status"] == "ACTION_REQUIRED"

    assert original_operator_profile_response.status_code == 200
    original_operator_profile_body = original_operator_profile_response.json()
    assert original_operator_profile_body["supportability_status"] == "HISTORICAL"
    assert original_operator_profile_body["review_transition_count"] == 1
    assert original_operator_profile_body["latest_review_actor"] == "review:banker.sg.sql.001"
    assert original_operator_profile_body["replacement_run_id"] == revised_run_id

    assert runtime_status_response.status_code == 200
    runtime_status_body = runtime_status_response.json()
    assert runtime_status_body["workflow_pack_run_store_mode"] == "sqlalchemy"
    assert runtime_status_body["workflow_pack_run_store"]["status"] == "READY"
    assert runtime_status_body["workflow_pack_task_flow_store_mode"] == "sqlalchemy"
    assert runtime_status_body["workflow_pack_task_flow_store"]["status"] == "READY"
    assert runtime_status_body["workflow_pack_runtime"]["run_summary"]["run_count"] == 2
    assert runtime_status_body["workflow_pack_runtime"]["run_summary"]["awaiting_review_count"] == 1
    assert runtime_status_body["workflow_pack_runtime"]["run_summary"]["superseded_count"] == 1
    assert runtime_status_body["workflow_pack_runtime"]["attention_queue"]["queue_depth"] == 1
    assert (
        runtime_status_body["workflow_pack_runtime"]["attention_queue"]["items"][0]["run_id"]
        == revised_run_id
    )

    assert task_flow_catalog_response.status_code == 200
    task_flow_catalog_body = task_flow_catalog_response.json()
    assert task_flow_catalog_body["task_flow_store_mode"] == "sqlalchemy"
    assert task_flow_catalog_body["task_flow_count"] == 2
    assert {
        run_id for flow in task_flow_catalog_body["task_flows"] for run_id in flow["run_refs"]
    } == {
        original_run_id,
        revised_run_id,
    }


def test_runtime_status_attention_queue_reports_full_backlog_depth(client: TestClient) -> None:
    for index in range(6):
        execute_response = client.post(
            "/ai/tasks/execute",
            json=advisor_brief_task_execution_request_json(
                correlation_id=f"corr-pack-run-api-queue-depth-00{index + 1}"
            ),
        )
        assert execute_response.status_code == 200

    runtime_status_response = client.get("/platform/runtime-status")

    assert runtime_status_response.status_code == 200
    runtime_status_body = runtime_status_response.json()
    attention_queue = runtime_status_body["workflow_pack_runtime"]["attention_queue"]
    assert attention_queue["queue_depth"] == 6
    assert attention_queue["queue_limit"] == 5
    assert len(attention_queue["items"]) == 5
    assert all(
        item["supportability_status"] == "ACTION_REQUIRED" for item in attention_queue["items"]
    )
    assert any(
        "use queue_depth to measure the full actionable backlog" in line
        for line in attention_queue["status_summary"]
    )
