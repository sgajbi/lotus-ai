from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness


def test_retrieval_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_retrieval_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.retrieval_mode == "disabled"
    assert readiness.embedding_provider_mode == "disabled"
    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 4
    assert len(readiness.activation_path) == 4
