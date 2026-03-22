from app.services.provider_activation_readiness import build_provider_activation_readiness


def test_provider_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_provider_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.activation_ready is False
    assert readiness.provider_mode == "disabled"
    assert readiness.embedding_provider_mode == "disabled"
    assert len(readiness.blocking_findings) == 4
    assert len(readiness.activation_path) == 4
