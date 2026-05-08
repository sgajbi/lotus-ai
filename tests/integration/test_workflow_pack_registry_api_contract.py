from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.support.runtime_settings import override_runtime_settings


def test_workflow_pack_registry_catalog_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert body["registration_count"] == 7
    assert body["registered_count"] == 6
    assert body["production_eligible_count"] == 0
    advisor_brief_registration = next(
        registration
        for registration in body["registrations"]
        if registration["pack_id"] == "advisor_brief.pack" and registration["version"] == "v1"
    )
    workspace_rationale_registration = next(
        registration
        for registration in body["registrations"]
        if registration["pack_id"] == "workspace_rationale.pack"
    )
    outcome_review_registration = next(
        registration
        for registration in body["registrations"]
        if registration["pack_id"] == "outcome_review_narrative.pack"
    )
    proof_pack_pm_memo_registration = next(
        registration
        for registration in body["registrations"]
        if registration["pack_id"] == "dpm_pm_memo.pack"
    )
    wave_pm_memo_registration = next(
        registration
        for registration in body["registrations"]
        if registration["pack_id"] == "dpm_wave_pm_memo.pack"
    )
    advisor_brief_binding = next(
        binding
        for binding in body["execution_bindings"]
        if binding["pack_id"] == "advisor_brief.pack"
    )
    workspace_rationale_binding = next(
        binding
        for binding in body["execution_bindings"]
        if binding["pack_id"] == "workspace_rationale.pack"
    )
    twr_inspection_binding = next(
        binding
        for binding in body["execution_bindings"]
        if binding["pack_id"] == "twr_inspection_support_brief.pack"
    )
    outcome_review_binding = next(
        binding
        for binding in body["execution_bindings"]
        if binding["pack_id"] == "outcome_review_narrative.pack"
    )
    proof_pack_pm_memo_binding = next(
        binding
        for binding in body["execution_bindings"]
        if binding["pack_id"] == "dpm_pm_memo.pack"
    )
    wave_pm_memo_binding = next(
        binding
        for binding in body["execution_bindings"]
        if binding["pack_id"] == "dpm_wave_pm_memo.pack"
    )
    advisor_brief_queue_policy = next(
        policy
        for policy in body["queue_policies"]
        if policy["workflow_pack_id"] == "advisor_brief.pack"
        and policy["workflow_pack_version"] == "v1"
    )
    outcome_review_queue_policy = next(
        policy
        for policy in body["queue_policies"]
        if policy["workflow_pack_id"] == "outcome_review_narrative.pack"
        and policy["workflow_pack_version"] == "v1"
    )
    proof_pack_pm_memo_queue_policy = next(
        policy
        for policy in body["queue_policies"]
        if policy["workflow_pack_id"] == "dpm_pm_memo.pack"
        and policy["workflow_pack_version"] == "v1"
    )
    wave_pm_memo_queue_policy = next(
        policy
        for policy in body["queue_policies"]
        if policy["workflow_pack_id"] == "dpm_wave_pm_memo.pack"
        and policy["workflow_pack_version"] == "v1"
    )

    assert advisor_brief_registration["registration_status"] == "REGISTERED"
    assert advisor_brief_registration["activation_state"] == "PILOT"
    assert workspace_rationale_registration["version"] == "v1"
    assert workspace_rationale_registration["owner_repository"] == "lotus-advise"
    assert workspace_rationale_registration["workflow_authority_owner"] == "lotus-advise"
    assert outcome_review_registration["version"] == "v1"
    assert outcome_review_registration["owner_repository"] == "lotus-manage"
    assert outcome_review_registration["workflow_authority_owner"] == "lotus-manage"
    assert outcome_review_registration["supported_callers"] == ["lotus-manage", "lotus-gateway"]
    assert proof_pack_pm_memo_registration["version"] == "v1"
    assert proof_pack_pm_memo_registration["owner_repository"] == "lotus-manage"
    assert proof_pack_pm_memo_registration["workflow_authority_owner"] == "lotus-manage"
    assert proof_pack_pm_memo_registration["supported_callers"] == [
        "lotus-manage",
        "lotus-gateway",
    ]
    assert wave_pm_memo_registration["version"] == "v1"
    assert wave_pm_memo_registration["owner_repository"] == "lotus-manage"
    assert wave_pm_memo_registration["workflow_authority_owner"] == "lotus-manage"
    assert wave_pm_memo_registration["supported_callers"] == [
        "lotus-manage",
        "lotus-gateway",
    ]
    assert advisor_brief_binding["version"] == "v1"
    assert advisor_brief_binding["task_id"] == "explain.v1"
    assert advisor_brief_binding["default_workflow_surface"] == "advisor-brief-workspace"
    assert advisor_brief_binding["required_payload_keys"] == [
        "performance",
        "period",
        "portfolio",
        "supportability",
    ]
    assert workspace_rationale_binding["version"] == "v1"
    assert workspace_rationale_binding["task_id"] == "explain.v1"
    assert workspace_rationale_binding["default_workflow_surface"] == "advisory-workspace-assistant"
    assert workspace_rationale_binding["required_payload_keys"] == [
        "evaluation_summary",
        "instruction",
        "proposal_status",
        "workspace",
    ]
    assert twr_inspection_binding["version"] == "v1"
    assert twr_inspection_binding["task_id"] == "explain.v1"
    assert twr_inspection_binding["default_workflow_surface"] == "twr-supportability-inspection"
    assert twr_inspection_binding["required_payload_keys"] == [
        "check_coverage",
        "evidence_summary",
        "findings",
        "inspection",
        "owner_summary",
    ]
    assert outcome_review_binding["version"] == "v1"
    assert outcome_review_binding["task_id"] == "explain.v1"
    assert outcome_review_binding["default_workflow_surface"] == "dpm-outcome-review-ai-evidence"
    assert outcome_review_binding["required_payload_keys"] == [
        "ai_evidence_input",
        "narrative_request",
        "supportability",
    ]
    assert proof_pack_pm_memo_binding["version"] == "v1"
    assert proof_pack_pm_memo_binding["task_id"] == "explain.v1"
    assert proof_pack_pm_memo_binding["default_workflow_surface"] == "dpm-proof-pack-ai-evidence"
    assert proof_pack_pm_memo_binding["required_payload_keys"] == [
        "ai_evidence_input",
        "memo_request",
        "supportability",
    ]
    assert wave_pm_memo_binding["version"] == "v1"
    assert wave_pm_memo_binding["task_id"] == "explain.v1"
    assert wave_pm_memo_binding["default_workflow_surface"] == "dpm-wave-ai-evidence"
    assert wave_pm_memo_binding["required_payload_keys"] == [
        "memo_request",
        "supportability",
        "wave_report_input",
    ]
    assert advisor_brief_queue_policy["default_lane"] == "LATENCY_SENSITIVE"
    assert advisor_brief_queue_policy["allowed_lanes"] == [
        "LATENCY_SENSITIVE",
        "REVIEW_SUPPORT",
    ]
    assert advisor_brief_queue_policy["max_concurrent_runs_per_pack"] == 4
    assert any(
        requirement["evidence_type"] == "capacity_evaluation"
        for requirement in advisor_brief_queue_policy["evidence_requirements"]
    )
    assert outcome_review_queue_policy["default_lane"] == "REVIEW_SUPPORT"
    assert outcome_review_queue_policy["allowed_lanes"] == ["REVIEW_SUPPORT", "OPERATOR"]
    assert proof_pack_pm_memo_queue_policy["default_lane"] == "REVIEW_SUPPORT"
    assert proof_pack_pm_memo_queue_policy["allowed_lanes"] == ["REVIEW_SUPPORT", "OPERATOR"]
    assert wave_pm_memo_queue_policy["default_lane"] == "REVIEW_SUPPORT"
    assert wave_pm_memo_queue_policy["allowed_lanes"] == ["REVIEW_SUPPORT", "OPERATOR"]


def test_workflow_pack_registration_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry/advisor_brief.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["pack_id"] == "advisor_brief.pack"
    assert body["registration"]["version"] == "v1"
    assert body["registration"]["owner_repository"] == "lotus-gateway"
    assert body["registration"]["workflow_authority_owner"] == "lotus-gateway"
    assert body["registration"]["definition_ref"] == (
        "repo://lotus-gateway/src/app/contracts/advisor_brief.py"
    )
    assert any(
        definition_ref["repository"] == "lotus-gateway"
        and definition_ref["path"] == "src/app/services/advisor_brief_service.py"
        and definition_ref["required_for_registration"] is True
        for definition_ref in body["registration"]["definition_refs"]
    )
    assert body["execution_binding"]["pack_id"] == "advisor_brief.pack"
    assert body["execution_binding"]["version"] == "v1"
    assert body["execution_binding"]["task_id"] == "explain.v1"
    assert body["execution_binding"]["default_workflow_surface"] == "advisor-brief-workspace"
    assert body["queue_policy"]["policy_id"] == "queue-policy.advisor-brief.v1"
    assert body["queue_policy"]["default_lane"] == "LATENCY_SENSITIVE"
    assert body["queue_policy"]["degraded_readiness_behavior"] == "REJECT"
    assert body["denied_without_registration"] is True
    assert any(
        rule["rule_id"] == "registered_entries_require_scope" for rule in body["validation_rules"]
    )


def test_workspace_rationale_registration_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry/workspace_rationale.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["pack_id"] == "workspace_rationale.pack"
    assert body["registration"]["version"] == "v1"
    assert body["registration"]["owner_repository"] == "lotus-advise"
    assert body["registration"]["workflow_authority_owner"] == "lotus-advise"
    assert body["registration"]["definition_ref"] == (
        "repo://lotus-advise/src/api/workspaces/router.py"
    )
    assert any(
        definition_ref["repository"] == "lotus-advise"
        and definition_ref["path"] == "src/api/services/workspace_ai_service.py"
        and definition_ref["required_for_registration"] is True
        for definition_ref in body["registration"]["definition_refs"]
    )
    assert body["execution_binding"]["pack_id"] == "workspace_rationale.pack"
    assert body["execution_binding"]["version"] == "v1"
    assert body["execution_binding"]["task_id"] == "explain.v1"
    assert body["execution_binding"]["default_workflow_surface"] == "advisory-workspace-assistant"


def test_twr_inspection_support_brief_registration_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry/twr_inspection_support_brief.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["pack_id"] == "twr_inspection_support_brief.pack"
    assert body["registration"]["version"] == "v1"
    assert body["registration"]["owner_repository"] == "lotus-performance"
    assert body["registration"]["workflow_authority_owner"] == "lotus-performance"
    assert body["registration"]["definition_ref"] == (
        "repo://lotus-performance/app/api/endpoints/inspections.py"
    )
    assert any(
        definition_ref["repository"] == "lotus-performance"
        and definition_ref["path"] == "app/services/inspection/twr_inspection_service.py"
        and definition_ref["required_for_registration"] is True
        for definition_ref in body["registration"]["definition_refs"]
    )
    assert body["execution_binding"]["pack_id"] == "twr_inspection_support_brief.pack"
    assert body["execution_binding"]["version"] == "v1"
    assert body["execution_binding"]["task_id"] == "explain.v1"
    assert body["execution_binding"]["default_workflow_surface"] == "twr-supportability-inspection"


def test_proof_pack_pm_memo_registration_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry/dpm_pm_memo.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["pack_id"] == "dpm_pm_memo.pack"
    assert body["registration"]["version"] == "v1"
    assert body["registration"]["owner_repository"] == "lotus-manage"
    assert body["registration"]["workflow_authority_owner"] == "lotus-manage"
    assert body["registration"]["definition_ref"] == (
        "repo://lotus-manage/src/core/proof_packs/handoffs.py"
    )
    assert any(
        definition_ref["repository"] == "lotus-manage"
        and definition_ref["path"] == "src/core/proof_packs/handoffs.py"
        and definition_ref["required_for_registration"] is True
        for definition_ref in body["registration"]["definition_refs"]
    )
    assert body["execution_binding"]["pack_id"] == "dpm_pm_memo.pack"
    assert body["execution_binding"]["version"] == "v1"
    assert body["execution_binding"]["task_id"] == "explain.v1"
    assert body["execution_binding"]["default_workflow_surface"] == "dpm-proof-pack-ai-evidence"


def test_wave_pm_memo_registration_detail_route(client: TestClient) -> None:
    response = client.get("/platform/workflow-packs/registry/dpm_wave_pm_memo.pack/v1")

    assert response.status_code == 200
    body = response.json()
    assert body["registration"]["pack_id"] == "dpm_wave_pm_memo.pack"
    assert body["registration"]["version"] == "v1"
    assert body["registration"]["owner_repository"] == "lotus-manage"
    assert body["registration"]["workflow_authority_owner"] == "lotus-manage"
    assert body["registration"]["definition_ref"] == (
        "repo://lotus-manage/src/core/waves/handoffs.py"
    )
    assert any(
        definition_ref["repository"] == "lotus-manage"
        and definition_ref["path"] == "src/core/waves/handoffs.py"
        and definition_ref["required_for_registration"] is True
        for definition_ref in body["registration"]["definition_refs"]
    )
    assert body["execution_binding"]["pack_id"] == "dpm_wave_pm_memo.pack"
    assert body["execution_binding"]["version"] == "v1"
    assert body["execution_binding"]["task_id"] == "explain.v1"
    assert body["execution_binding"]["default_workflow_surface"] == "dpm-wave-ai-evidence"


def test_workflow_pack_registration_detail_route_rejects_unknown_registration(
    client: TestClient,
) -> None:
    response = client.get("/platform/workflow-packs/registry/unknown.pack/v1")

    assert response.status_code == 404
    assert "Unknown workflow-pack registration" in response.json()["detail"]


def test_workflow_pack_registry_routes_degrade_when_sql_store_is_unmigrated(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-registry-unmigrated-api.db'}"

    with override_runtime_settings(
        workflow_pack_registry_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        with TestClient(app) as durable_client:
            catalog_response = durable_client.get("/platform/workflow-packs/registry")
            detail_response = durable_client.get(
                "/platform/workflow-packs/registry/advisor_brief.pack/v1"
            )

    assert catalog_response.status_code == 503
    assert detail_response.status_code == 503
    assert "Workflow-pack registry store is not ready." in catalog_response.json()["detail"]
    assert "MIGRATION_REQUIRED" in catalog_response.json()["detail"]
    assert "workflow_pack_registrations" in catalog_response.json()["detail"]
    assert "Workflow-pack registry store is not ready." in detail_response.json()["detail"]
