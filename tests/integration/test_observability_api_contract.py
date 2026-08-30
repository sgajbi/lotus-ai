from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.config import settings
from app.services.audit_store import get_audit_store


def test_observability_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/observability/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["domain_count"] == 6
    assert body["ai_surface_supportability"]["supported_surface_count"] == 17
    assert body["ai_surface_supportability"]["executable_workflow_pack_count"] == 17
    assert (
        body["ai_surface_supportability"]["metric_name"] == "lotus_ai_surface_supportability_state"
    )
    assert body["ai_surface_supportability"]["metric_labels"] == ["surface", "posture", "source"]
    assert {
        surface["workflow_pack_ref"] for surface in body["ai_surface_supportability"]["surfaces"]
    } == {
        "advisor_brief.pack@v1",
        "advisory_copilot_client_follow_up_draft.pack@v1",
        "advisory_copilot_compliance_review_summary.pack@v1",
        "advisory_copilot_evidence_qa.pack@v1",
        "advisory_copilot_meeting_preparation.pack@v1",
        "advisory_copilot_operations_report_handoff.pack@v1",
        "advisory_copilot_proposal_explanation.pack@v1",
        "dpm_exception_summary.pack@v1",
        "dpm_operations_handoff_summary.pack@v1",
        "dpm_pm_memo.pack@v1",
        "dpm_wave_pm_memo.pack@v1",
        "idea_explanation.pack@v1",
        "outcome_review_narrative.pack@v1",
        "pm_quality_summary.pack@v1",
        "proposal_memo_commentary.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    }
    assert any(
        surface["surface_id"] == "dpm_exception_summary"
        and surface["owning_service"] == "lotus-manage"
        and surface["workflow_authority_owner"] == "lotus-manage"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "dpm_operations_handoff_summary"
        and surface["owning_service"] == "lotus-manage"
        and surface["workflow_authority_owner"] == "lotus-manage"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "idea_explanation"
        and surface["owning_service"] == "lotus-idea"
        and surface["workflow_authority_owner"] == "lotus-idea"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "dpm_pm_memo"
        and surface["owning_service"] == "lotus-manage"
        and surface["workflow_authority_owner"] == "lotus-manage"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "dpm_wave_pm_memo"
        and surface["owning_service"] == "lotus-manage"
        and surface["workflow_authority_owner"] == "lotus-manage"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "outcome_review_narrative"
        and surface["owning_service"] == "lotus-manage"
        and surface["workflow_authority_owner"] == "lotus-manage"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "pm_quality_summary"
        and surface["owning_service"] == "lotus-manage"
        and surface["workflow_authority_owner"] == "lotus-manage"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "proposal_memo_commentary"
        and surface["owning_service"] == "lotus-advise"
        and surface["workflow_authority_owner"] == "lotus-advise"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert any(
        surface["surface_id"] == "advisory_copilot_proposal_explanation"
        and surface["owning_service"] == "lotus-advise"
        and surface["workflow_authority_owner"] == "lotus-advise"
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert {
        surface["supportability_reason"]
        for surface in body["ai_surface_supportability"]["surfaces"]
    } == {"WORKFLOW_PACK_SUPPORTED_NO_ACTIVITY"}
    assert all(
        surface["no_sensitive_content_telemetry"] is True
        for surface in body["ai_surface_supportability"]["surfaces"]
    )
    assert body["unavailable_domain_count"] == 0
    assert body["incident_evidence_supported_domain_count"] >= 1
    assert any(domain["domain_id"] == "provider" for domain in body["domains"])
    assert any(domain["domain_id"] == "safety" for domain in body["domains"])
    assert any(
        item["evidence_id"] == "safety_runtime_enforcement_state"
        for item in body["incident_evidence_items"]
    )
    assert all(item["artifact_refs"] for item in body["incident_evidence_items"])


def test_observability_governance_routes(client: TestClient) -> None:
    activation_response = client.get("/platform/observability/activation-readiness")
    assert activation_response.status_code == 200
    activation_body = activation_response.json()
    assert activation_body["activation_ready"] is False
    assert activation_body["domain_count"] == 6
    # Issue #150 slice 2: active redaction telemetry no longer blocks
    # observability activation.
    assert not any(
        "no-sensitive-content telemetry" in finding
        for finding in activation_body["blocking_findings"]
    )

    runbook_response = client.get("/platform/observability/runbook-readiness")
    assert runbook_response.status_code == 200
    runbook_body = runbook_response.json()
    assert runbook_body["runbook_ready"] is True
    assert runbook_body["required_item_count"] == 3

    governance_response = client.get("/platform/observability/governance-status")
    assert governance_response.status_code == 200
    governance_body = governance_response.json()
    assert governance_body["governance_ready"] is False
    assert governance_body["activation_readiness"]["activation_ready"] is False
    assert not any(
        "no-sensitive-content telemetry" in finding
        for finding in governance_body["activation_readiness"]["blocking_findings"]
    )
    assert governance_body["runbook_readiness"]["runbook_ready"] is True
    assert governance_body["runtime_status"]["domain_count"] == 6


def test_observability_incident_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/incident-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["domain_count"] == 6
    assert any(summary["domain_id"] == "provider" for summary in body["summaries"])
    assert any(summary["domain_id"] == "retrieval" for summary in body["summaries"])
    assert any(summary["domain_id"] == "async" for summary in body["summaries"])
    assert any(summary["domain_id"] == "evaluation" for summary in body["summaries"])
    assert any(summary["domain_id"] == "prompt" for summary in body["summaries"])
    assert any(summary["domain_id"] == "safety" for summary in body["summaries"])
    assert all(
        summary["incident_evidence_items"][0]["artifact_refs"] for summary in body["summaries"]
    )
    retrieval_summary = next(
        summary for summary in body["summaries"] if summary["domain_id"] == "retrieval"
    )
    assert len(retrieval_summary["incident_evidence_items"]) == 2


def test_provider_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/provider-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "provider"
    assert body["telemetry"]["incident_evidence_supported"] is True
    assert body["incident_evidence_items"][0]["evidence_id"] == "provider_operations_incident_state"
    assert len(body["incident_evidence_items"][0]["artifact_refs"]) == 1


def test_evaluation_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/evaluation-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "evaluation"
    assert body["incident_evidence_items"][0]["evidence_id"] == "evaluation_approval_gate_state"
    assert len(body["incident_evidence_items"][0]["artifact_refs"]) == 1


def test_prompt_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/prompt-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "prompt"
    assert body["incident_evidence_items"][0]["evidence_id"] == "prompt_rollout_approval_state"
    assert len(body["incident_evidence_items"][0]["artifact_refs"]) == 1


def test_safety_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/safety-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "safety"
    assert body["incident_evidence_items"][0]["evidence_id"] == "safety_runtime_enforcement_state"
    assert len(body["incident_evidence_items"][0]["artifact_refs"]) == 1


def _seed_two_tenant_executions(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-observe-breakdown-1",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-advise",
                "correlation_id": "corr-observe-breakdown-2",
                "tenant_id": "tenant-us-002",
            },
            "context": {
                "summary": "Explain portfolio state",
                "payload": {"status": "OK"},
                "source_refs": [],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )


def test_breakdowns_require_privileged_identity_for_all_tenant_inspection(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    _seed_two_tenant_executions(client)
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)

    response = client.get(
        "/platform/observability/breakdowns",
        params={"limit": 50},
        headers={"X-Caller-App": "lotus-platform"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_scope"] == "ALL_TENANTS"
    assert body["sampled_audit_record_limit"] == 50
    assert body["sampled_audit_record_count"] >= 2
    assert any(sample["caller_app"] == "lotus-manage" for sample in body["caller_apps"])
    assert any(sample["tenant_id"] == "tenant-sg-001" for sample in body["tenants"])
    assert any(sample["tenant_id"] == "tenant-us-002" for sample in body["tenants"])
    assert any(
        sample["capability_kind"] == "TASK" and sample["capability_id"] == "knowledge_answer.v1"
        for sample in body["capabilities"]
    )

    # The all-tenant inspection leaves a durable access event, like /ai/audit.
    events = get_audit_store().list_access_events()
    assert any(
        event.operation.value == "AGGREGATE_BREAKDOWNS"
        and event.caller_app == "lotus-platform"
        and event.outcome.value == "SUCCEEDED"
        for event in events
    )


def test_breakdowns_are_tenant_scoped_for_restricted_callers(client: TestClient) -> None:
    """The #168 reproduction, inverted into a guarantee: a caller restricted to
    tenant-sg-001 must never see tenant-us-002 in the tenants array."""

    _seed_two_tenant_executions(client)

    response = client.get(
        "/platform/observability/breakdowns",
        params={"limit": 50},
        headers={"X-Caller-App": "lotus-idea"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_scope"] == "RESTRICTED_TENANTS"
    tenant_ids = {sample["tenant_id"] for sample in body["tenants"]}
    assert "tenant-us-002" not in tenant_ids
    assert tenant_ids <= {"tenant-sg-001", ""}
    # Scoped utility is preserved: the caller still sees its own tenant's records.
    assert body["sampled_audit_record_count"] >= 1


def test_breakdowns_fail_when_the_access_evidence_cannot_be_written(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    """Evidence is not optional: if the all-tenant access event cannot be
    recorded, the privileged read fails rather than serving unevidenced data."""

    import pytest

    _seed_two_tenant_executions(client)
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)

    def _refuse_event(event: object) -> None:
        raise RuntimeError("access-event store unavailable")

    monkeypatch.setattr(get_audit_store(), "save_access_event", _refuse_event)

    with pytest.raises(RuntimeError, match="access-event store unavailable"):
        client.get(
            "/platform/observability/breakdowns",
            headers={"X-Caller-App": "lotus-platform"},
        )


def test_breakdowns_fail_closed_for_unknown_and_unprivileged_callers(
    client: TestClient,
) -> None:
    unknown = client.get(
        "/platform/observability/breakdowns",
        headers={"X-Caller-App": "lotus-unknown-app"},
    )
    assert unknown.status_code == 403

    # lotus-platform holds the all-tenant capability, but a header-only
    # identity is not privileged under the default posture: fail closed.
    header_only_privileged = client.get(
        "/platform/observability/breakdowns",
        headers={"X-Caller-App": "lotus-platform"},
    )
    assert header_only_privileged.status_code == 403


def test_retrieval_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/retrieval-summary")
    assert response.status_code == 200
    assert response.json()["service"] == "lotus-ai"


def test_async_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/async-summary")
    assert response.status_code == 200
    assert response.json()["service"] == "lotus-ai"
