from app.services.observability_runtime import build_observability_runtime_status


def test_build_observability_runtime_status_returns_bounded_domain_summary() -> None:
    status = build_observability_runtime_status()

    assert status.service == "lotus-ai"
    assert status.domain_count == 6
    assert status.ai_surface_supportability.supported_surface_count == 4
    assert status.ai_surface_supportability.executable_workflow_pack_count == 4
    assert status.ai_surface_supportability.no_sensitive_content_telemetry is False
    assert status.ai_surface_supportability.metric_name == "lotus_ai_surface_supportability_state"
    assert status.ai_surface_supportability.metric_labels == ["surface", "posture", "source"]
    assert {surface.workflow_pack_ref for surface in status.ai_surface_supportability.surfaces} == {
        "advisor_brief.pack@v1",
        "outcome_review_narrative.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    }
    assert any(
        surface.surface_id == "outcome_review_narrative"
        and surface.owning_service == "lotus-manage"
        and surface.workflow_authority_owner == "lotus-manage"
        for surface in status.ai_surface_supportability.surfaces
    )
    assert {
        surface.supportability_reason.value for surface in status.ai_surface_supportability.surfaces
    } == {"NO_SENSITIVE_TELEMETRY_DEGRADED"}
    assert all(
        surface.no_sensitive_content_telemetry is False
        for surface in status.ai_surface_supportability.surfaces
    )
    assert status.healthy_domain_count >= 1
    assert status.degraded_domain_count >= 1
    assert status.unavailable_domain_count == 0
    assert status.incident_evidence_supported_domain_count >= 4
    assert any(domain.domain_id == "provider" for domain in status.domains)
    assert any(domain.domain_id == "safety" for domain in status.domains)
    assert any(
        item.evidence_id == "safety_runtime_enforcement_state"
        for item in status.incident_evidence_items
    )
    assert any(
        item.evidence_id == "provider_operations_incident_state"
        for item in status.incident_evidence_items
    )
    assert any(
        item.evidence_id == "evaluation_approval_gate_state"
        for item in status.incident_evidence_items
    )
    assert any("deployment-split posture" in line.lower() for line in status.status_summary)
    assert any("ai surface supportability" in line.lower() for line in status.status_summary)


def test_build_observability_runtime_status_flags_async_degradation() -> None:
    status = build_observability_runtime_status()
    async_domain = next(domain for domain in status.domains if domain.domain_id == "async")

    assert async_domain.breakdown_support.caller_app_supported is True
    assert async_domain.breakdown_support.capability_supported is True
    assert any("worker identity" in line for line in async_domain.status_summary)
