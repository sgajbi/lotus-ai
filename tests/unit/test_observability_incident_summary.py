from app.services.observability_incident_summary import build_observability_incident_summary


def test_observability_incident_summary_covers_provider_retrieval_and_async() -> None:
    summary = build_observability_incident_summary()

    assert summary.service == "lotus-ai"
    assert summary.domain_count == 6
    assert any(item.domain_id == "provider" for item in summary.summaries)
    assert any(item.domain_id == "retrieval" for item in summary.summaries)
    assert any(item.domain_id == "async" for item in summary.summaries)
    assert any(item.domain_id == "evaluation" for item in summary.summaries)
    assert any(item.domain_id == "prompt" for item in summary.summaries)
    assert any(item.domain_id == "safety" for item in summary.summaries)
    assert all(
        domain.incident_evidence_items[0].artifact_refs
        for domain in summary.summaries
    )
