from app.contracts.observability import ObservabilityPosture
from app.services.ai_surface_supportability import build_ai_surface_supportability_summary


def test_ai_surface_supportability_summary_is_source_backed_and_bounded() -> None:
    summary = build_ai_surface_supportability_summary()

    assert summary.posture == ObservabilityPosture.DEGRADED
    assert summary.supported_surface_count == 3
    assert summary.executable_workflow_pack_count == 3
    assert summary.action_required_surface_count == 3
    assert summary.unavailable_surface_count == 0
    assert summary.no_sensitive_content_telemetry is False
    assert summary.metric_name == "lotus_ai_surface_supportability_state"
    assert {item.surface_id: item.owning_service for item in summary.surfaces} == {
        "advisor_brief": "lotus-advise",
        "twr_inspection_support_brief": "lotus-performance",
        "workspace_rationale": "lotus-workbench",
    }
    assert all(item.workflow_authority_owner != "lotus-ai" for item in summary.surfaces)
    assert all(
        "/platform/workflow-packs/runs" in item.source_endpoints for item in summary.surfaces
    )
    assert any("No-sensitive-content telemetry" in line for line in summary.status_summary)
