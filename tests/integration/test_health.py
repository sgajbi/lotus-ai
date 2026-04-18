from fastapi.testclient import TestClient
from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.main import app


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_correlation_header_propagation(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_service_root_and_metadata_routes_expose_workflow_pack_platform_truth(
    client: TestClient,
) -> None:
    root_response = client.get("/")
    metadata_response = client.get("/metadata")

    assert root_response.status_code == 200
    assert metadata_response.status_code == 200
    root_body = root_response.json()
    metadata_body = metadata_response.json()
    assert "workflow_packs" in root_body["capabilityAreas"]
    assert "workflow_pack_runs" in root_body["capabilityAreas"]
    assert metadata_body["service"] == "lotus-ai"
    assert metadata_body["workflowPackRunStoreMode"] == "memory"
    assert "startupReadinessPolicy" in metadata_body
    assert "readinessProbePolicy" in metadata_body


def test_health_ready_returns_draining_when_service_is_draining(client: TestClient) -> None:
    app.state.is_draining = True
    try:
        response = client.get("/health/ready")
    finally:
        app.state.is_draining = False

    assert response.status_code == 503
    assert response.json()["status"] == "draining"


def test_health_ready_returns_degraded_when_probe_policy_requires_it(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "readiness_probe_policy", "degrade")
    prior_findings = getattr(app.state, "startup_readiness_findings", [])
    app.state.startup_readiness_findings = ["database unavailable"]
    try:
        response = client.get("/health/ready")
    finally:
        app.state.startup_readiness_findings = prior_findings

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_platform_capabilities_contract(client: TestClient) -> None:
    response = client.get("/platform/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert any(task["task_id"] == "explain.v1" for task in body["tasks"])


def test_platform_capability_pack_catalog_contract(client: TestClient) -> None:
    response = client.get("/platform/capability-packs")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert body["pack_count"] == 2
    assert body["reusable_pack_count"] == 1
    assert body["approved_pack_count"] == 0
    assert body["packs"][0]["pack_id"] == "analytics_commentary.pack.v1"
    assert body["packs"][0]["maturity_stage"] == "REUSABLE"
    assert body["packs"][1]["pack_id"] == "decision_explanation.pack.v1"


def test_platform_workflow_pack_registry_contract(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert body["registration_count"] == 2
    assert body["registered_count"] == 1
    assert body["registrations"][0]["pack_id"] == "advisor_brief.pack"
    assert body["registrations"][0]["activation_state"] == "PILOT"

    eligibility_response = client.post(
        "/platform/workflow-packs/eligibility/evaluate",
        json={
            "pack_id": "advisor_brief.pack",
            "version": "v1",
            "caller_app": "lotus-gateway",
            "environment": "QA",
            "caller_identity_class": "INTERNAL_SERVICE",
            "workflow_surface": "advisor-brief-panel",
        },
    )
    assert eligibility_response.status_code == 200
    assert eligibility_response.json()["eligibility_result"] == "ALLOWED"

    control_history_response = client.get("/platform/workflow-packs/control-history")
    assert control_history_response.status_code == 200
    assert "PAUSE" in control_history_response.json()["supported_action_types"]


def test_platform_app_capability_rollout_catalog_contract(client: TestClient) -> None:
    response = client.get("/platform/app-capability-rollouts")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["pairing_count"] == 4
    assert body["onboarded_pairing_count"] == 1
    assert body["active_pairing_count"] == 0
    assert body["rollout_records"][0]["downstream_app"] == "lotus-performance"
    assert body["rollout_records"][0]["rollout_stage"] == "INTEGRATION_IN_PROGRESS"
    assert body["rollout_records"][1]["downstream_app"] == "lotus-manage"
    assert body["rollout_records"][1]["rollout_stage"] == "NOT_ONBOARDED"
    governance_response = client.get("/platform/app-capability-rollouts/governance-status")
    assert governance_response.status_code == 200
    assert governance_response.json()["ready_pairing_count"] == 1
    assert governance_response.json()["blocking_pairing_count"] == 3
    observability_response = client.get("/platform/app-capability-rollouts/observability-summary")
    assert observability_response.status_code == 200
    assert observability_response.json()["pairing_count"] == 4
    assert observability_response.json()["blocked_pairing_count"] == 4
    lifecycle_response = client.get("/platform/app-capability-rollouts/lifecycle-status")
    assert lifecycle_response.status_code == 200
    assert lifecycle_response.json()["ready_pairing_count"] == 1
    assert lifecycle_response.json()["blocking_pairing_count"] == 3
    onboarding_response = client.get(
        "/platform/app-capability-rollouts/lotus-performance/analytics_commentary.pack.v1/onboarding-template"
    )
    assert onboarding_response.status_code == 200
    assert onboarding_response.json()["reference_use_case_template_id"] == (
        "bounded_explanation_only_onboarding.v1"
    )


def test_first_production_use_case_contract(client: TestClient) -> None:
    response = client.get("/platform/use-cases/first-production-use-case")

    assert response.status_code == 200
    body = response.json()
    assert body["downstream_app"] == "lotus-performance"
    assert body["task_id"] == "explain.v1"
    assert body["rollout_posture"] == "CONTRACT_DEFINED"


def test_task_execution_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-summary-route-1",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Explain rebalance outcome",
                "payload": {"status": "BLOCKED"},
                "source_refs": [],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    )
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-summary-route-2",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Search Lotus knowledge sources",
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

    response = client.get("/platform/tasks/execution-summary", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["sampled_record_limit"] == 20
    assert body["sampled_record_count"] >= 2
    assert body["stubbed_execution_count"] >= 1
    assert body["non_stubbed_execution_count"] >= 1
    assert any(sample["provider_mode"] == "catalog_only" for sample in body["provider_modes"])
    assert any(sample["provider_mode"] != "catalog_only" for sample in body["provider_modes"])


def test_task_execution_evidence_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-evidence-route-1",
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
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-evidence-route-2",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    response = client.get("/platform/tasks/evidence-summary", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["sampled_record_limit"] == 20
    assert body["sampled_record_count"] >= 2
    assert body["citation_bearing_execution_count"] >= 2
    assert body["citation_backed_answer_count"] >= 1
    assert body["refused_answer_count"] >= 1
    assert any(sample["answer_mode"] == "CITATION_BACKED" for sample in body["answer_modes"])
    assert any(
        sample["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT" for sample in body["answer_modes"]
    )


def test_task_retrieval_execution_summary_route(client: TestClient) -> None:
    client.post(
        "/ai/tasks/execute",
        json={
            "task_id": "knowledge_search.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-rsummary-route-1",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Search Lotus knowledge sources",
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
            "task_id": "knowledge_answer.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-manage",
                "correlation_id": "corr-rsummary-route-2",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Answer from Lotus knowledge sources",
                "payload": {
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                "source_refs": [],
            },
            "expected_output_label": "RETRIEVAL_ANSWER",
        },
    )

    response = client.get("/platform/tasks/retrieval-summary", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["sampled_record_limit"] == 20
    assert body["sampled_record_count"] >= 2
    assert body["retrieval_execution_count"] >= 2
    assert body["knowledge_search_execution_count"] >= 1
    assert body["knowledge_answer_execution_count"] >= 1
    assert body["refused_answer_count"] >= 1
    assert any(sample["retrieval_status"] == "READY" for sample in body["retrieval_statuses"])
    assert any(sample["source_id"] == "lotus-platform-rfcs" for sample in body["sources"])
    assert any(
        sample["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT" for sample in body["answer_modes"]
    )


def test_platform_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["delivery_phase"] == "foundation"
    assert body["startup_readiness_policy"] == "warn"
    assert body["readiness_probe_policy"] == "observe"
    assert body["audit_store"]["mode"] == "memory"
    assert body["audit_store"]["status"] == "READY"
    assert body["retrieval_store"]["mode"] == "memory"
    assert body["retrieval_store"]["status"] == "READY"
    assert body["access_control_store_mode"] == "memory"
    assert body["workflow_pack_run_store_mode"] == "memory"
    assert body["workflow_pack_run_store"]["mode"] == "memory"
    assert body["workflow_pack_run_store"]["status"] == "READY"
    assert body["access_control_runtime"]["store_mode"] == "memory"
    assert body["access_control_runtime"]["enforcement_state"] == "FULLY_ENFORCED"
    assert body["access_control_runtime"]["data_plane_enforced"] is True
    assert body["access_control_runtime"]["control_plane_enforced"] is True
    assert body["access_control_runtime"]["policy_count"] >= 5
    assert body["access_control_runtime"]["tenant_isolation_active"] is True
    assert body["access_control_governance"]["governance_ready"] is False
    assert body["access_control_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["access_control_governance"]["runbook_readiness"]["runbook_ready"] is True
    assert body["access_control_governance"]["blocking_area_count"] == 1
    assert body["observability_runtime"]["domain_count"] == 6
    assert body["observability_runtime"]["unavailable_domain_count"] == 0
    assert body["observability_runtime"]["incident_evidence_supported_domain_count"] >= 1
    assert body["observability_governance"]["governance_ready"] is False
    assert body["observability_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["observability_governance"]["runbook_readiness"]["runbook_ready"] is True
    assert body["observability_governance"]["blocking_area_count"] == 1
    assert body["async_runtime"]["cutover_state"] == "in_process_only"
    assert body["async_runtime"]["queue_mode"] == "DISABLED"
    assert body["async_runtime"]["worker_mode"] == "IN_PROCESS_ONLY"
    assert body["async_runtime"]["supported_queue_backends"][0]["backend_id"] == "none"
    assert body["async_runtime"]["supported_queue_backends"][1]["backend_id"] == "redis_queue"
    assert body["async_runtime"]["queue_backend"] == "none"
    assert body["async_runtime"]["active_worker_execution"] == "in_process_stub"
    assert (
        body["async_runtime"]["supported_worker_executions"][2]["worker_id"]
        == "queue_backed_workers"
    )
    assert body["async_runtime"]["active_worker_count"] == 0
    assert body["async_runtime"]["active_worker_ids"] == []
    assert body["async_runtime"]["enqueued_job_count"] == 0
    assert body["async_runtime"]["recorded_job_count"] == 2
    assert body["async_runtime"]["queue_backlog_count"] == 0
    assert body["async_runtime"]["duplicate_delivery_count"] == 0
    assert body["async_runtime"]["redelivery_count"] == 0
    assert body["async_runtime"]["drain_mode_active"] is False
    assert body["async_runtime"]["degraded_findings"] == []
    assert "current cutover state exposes" in body["async_runtime"]["message"]
    assert body["async_governance"]["governance_ready"] is False
    assert body["async_governance"]["blocking_area_count"] == 2
    assert body["async_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["async_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["async_governance"]["runbook_readiness"]["completed_required_item_count"] == 3
    assert body["provider_governance"]["governance_ready"] is False
    assert body["provider_governance"]["blocking_area_count"] == 3
    assert body["provider_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["provider_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["provider_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["provider_operations"]["operations_state"] == "ROLLOUT_BLOCKED"
    assert body["provider_operations"]["runtime_execution_enabled"] is False
    assert body["provider_operations"]["quota_policy"]["quota_enforced"] is False
    assert body["provider_operations"]["budget_policy"]["budget_enforced"] is False
    assert body["retrieval_governance"]["governance_ready"] is False
    assert body["retrieval_governance"]["blocking_area_count"] == 3
    assert body["retrieval_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["retrieval_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["retrieval_governance"]["runbook_readiness"]["completed_required_item_count"] == 4
    assert body["retrieval_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["prompt_governance"]["governance_ready"] is False
    assert body["prompt_governance"]["blocking_area_count"] == 2
    assert body["prompt_governance"]["activation_readiness"]["activation_ready"] is False
    assert body["prompt_governance"]["runbook_readiness"]["runbook_ready"] is True
    assert body["prompt_governance"]["evidence_readiness"]["evidence_ready"] is False
    assert body["evaluation_runtime"]["manifest_version"] == "foundation.v1"
    assert body["evaluation_runtime"]["evidence_category_count"] == 6
    assert body["evaluation_runtime"]["staged_case_count"] == 46
    assert body["evaluation_runtime"]["seam_coverage"][0]["seam_id"] == "async_execution"
    assert body["evaluation_runtime"]["seam_coverage"][0]["staged_fixture_count"] == 1
    assert body["evaluation_runtime"]["seam_coverage"][1]["staged_fixture_count"] == 6
    assert body["evaluation_runtime"]["seam_coverage"][1]["staged_case_count"] == 12
    assert body["evaluation_runtime"]["seam_coverage"][2]["staged_fixture_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][2]["staged_case_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][3]["staged_fixture_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][3]["staged_case_count"] == 5
    assert body["evaluation_runtime"]["seam_coverage"][4]["staged_fixture_count"] == 6
    assert body["evaluation_runtime"]["seam_coverage"][4]["staged_case_count"] == 18
    assert body["evaluation_runtime"]["seam_coverage"][5]["staged_fixture_count"] == 2
    assert body["evaluation_runtime"]["seam_coverage"][5]["staged_case_count"] == 6
    assert body["evaluation_runtime"]["approval_gates"][0]["domain_id"] == (
        "first_use_case_onboarding"
    )
    assert body["evaluation_runtime"]["approval_gates"][1]["domain_id"] == "prompt_rollout"
    assert body["evaluation_runtime"]["approval_gates"][2]["domain_id"] == "retrieval_execution"
    assert body["evaluation_runtime"]["approval_gates"][3]["domain_id"] == "provider_execution"
    assert body["evaluation_runtime"]["approval_gates"][4]["domain_id"] == "safety_enforcement"
    assert (
        body["evaluation_runtime"]["approval_gates"][5]["domain_id"] == "analytics_commentary_pack"
    )
    assert (
        body["evaluation_runtime"]["approval_gates"][6]["domain_id"] == "decision_explanation_pack"
    )
    assert body["evaluation_runtime"]["recorded_run_count"] == 2
    assert body["evaluation_runtime"]["latest_recorded_run_id"] == "foundation_eval_2026_03_22_001"
    assert body["evaluation_runtime"]["evaluation_runner_active"] is True
    assert body["prompt_runtime"]["selection_mode"] == "ROLLOUT_STATE_ACTIVE"
    assert body["prompt_runtime"]["rollout_mode"] == "GOVERNED_CONTROL_ACTIONS"
    assert body["prompt_runtime"]["active_prompt_count"] >= 7
    assert body["prompt_runtime"]["candidate_prompt_count"] == 0
    assert any(
        selection["task_id"] == "explain.v1" for selection in body["prompt_runtime"]["selections"]
    )
    assert any(
        state["task_id"] == "explain.v1" for state in body["prompt_runtime"]["rollout_states"]
    )
    assert body["task_runtime"]["enabled_task_count"] >= 7
    assert body["task_runtime"]["retrieval_backed_task_count"] == 2
    assert body["capability_pack_count"] == 2
    assert body["capability_pack_catalog"]["pack_count"] == 2
    assert body["capability_pack_catalog"]["reusable_pack_count"] == 1
    assert body["capability_pack_catalog"]["packs"][0]["pack_id"] == "analytics_commentary.pack.v1"
    assert body["capability_pack_catalog"]["packs"][0]["maturity_stage"] == "REUSABLE"
    assert (
        body["capability_pack_catalog"]["packs"][0]["quality_gate_domain_id"]
        == "analytics_commentary_pack"
    )
    assert body["capability_pack_catalog"]["packs"][1]["pack_id"] == "decision_explanation.pack.v1"
    assert body["capability_pack_governance"]["ready_pack_count"] == 0
    assert body["capability_pack_governance"]["blocking_pack_count"] == 2
    assert body["app_capability_rollout_catalog"]["pairing_count"] == 4
    assert body["app_capability_rollout_governance"]["ready_pairing_count"] == 1
    assert body["app_capability_rollout_observability"]["pairing_count"] == 4
    assert body["app_capability_rollout_observability"]["blocked_pairing_count"] == 4
    assert body["app_capability_rollout_lifecycle"]["ready_pairing_count"] == 1
    assert body["app_capability_rollout_lifecycle"]["blocking_pairing_count"] == 3
    assert body["app_capability_rollout_observed_count"] >= 0
    assert body["app_capability_rollout_lifecycle_ready_count"] == 1
    assert body["first_use_case"]["use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["first_use_case"]["downstream_app"] == "lotus-performance"
    assert body["first_use_case"]["capability_pack_id"] == "analytics_commentary.pack.v1"
    assert body["first_use_case"]["capability_pack_family_id"] == "analytics_commentary"
    assert body["first_use_case"]["contract_hardened"] is True
    assert body["first_use_case_governance"]["rollout_stage"] == "PRE_PROD_VALIDATION"
    assert body["first_use_case_governance"]["operational_posture"] == "LIMITED_ROLLOUT_BLOCKED"
    assert body["first_use_case_governance"]["active_production_ready"] is False
    assert body["first_use_case_governance"]["governance_ready"] is False
    assert body["first_use_case_governance"]["readiness"]["readiness_ready"] is False
    assert body["first_use_case_governance"]["runbook_readiness"]["runbook_ready"] is True
    assert any(
        task["task_id"] == "knowledge_search.v1" and task["stubbed"] is False
        for task in body["task_runtime"]["tasks"]
    )
    assert body["safety_runtime"]["runtime_redaction_active"] is False
    assert body["safety_runtime"]["enforced_control_ids"] == [
        "response_labeling",
        "correlation_and_audit",
    ]
    assert body["safety_governance"]["governance_ready"] is False
    assert body["safety_governance"]["blocking_area_count"] == 3
    assert body["safety_governance"]["runtime_status"]["runtime_redaction_active"] is False
    assert body["safety_governance"]["runbook_readiness"]["runbook_ready"] is False
    assert body["safety_governance"]["runbook_readiness"]["completed_required_item_count"] == 3
    assert body["safety_governance"]["evidence_readiness"]["approval_gate"]["domain_id"] == (
        "safety_enforcement"
    )
    assert body["migration_contract_enforced"] is True
    assert body["startup_readiness_blocking"] is False
    assert body["prompt_count"] >= 3


def test_service_metadata_exposes_store_modes(client: TestClient) -> None:
    response = client.get("/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["auditStoreMode"] == "memory"
    assert body["promptStoreMode"] == "memory"
    assert body["retrievalStoreMode"] == "memory"
    assert body["accessControlStoreMode"] == "memory"
    assert body["workflowPackRunStoreMode"] == "memory"
    assert body["startupReadinessPolicy"] == "warn"
    assert body["readinessProbePolicy"] == "observe"
