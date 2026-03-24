from app.services.observability_runtime import build_observability_runtime_status


def test_build_observability_runtime_status_returns_bounded_domain_summary() -> None:
    status = build_observability_runtime_status()

    assert status.service == "lotus-ai"
    assert status.domain_count == 6
    assert status.healthy_domain_count >= 1
    assert status.degraded_domain_count >= 1
    assert status.unavailable_domain_count == 0
    assert status.incident_evidence_supported_domain_count >= 4
    assert any(domain.domain_id == "provider" for domain in status.domains)
    assert any(domain.domain_id == "safety" for domain in status.domains)
    assert any(item.evidence_id == "safety_audit_evidence_pack" for item in status.incident_evidence_items)
    assert any(item.evidence_id == "provider_operations_incident_state" for item in status.incident_evidence_items)


def test_build_observability_runtime_status_flags_async_degradation() -> None:
    status = build_observability_runtime_status()
    async_domain = next(domain for domain in status.domains if domain.domain_id == "async")

    assert async_domain.breakdown_support.caller_app_supported is True
    assert async_domain.breakdown_support.capability_supported is True
    assert any("worker identity" in line for line in async_domain.status_summary)
