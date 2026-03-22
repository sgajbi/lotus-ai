from app.services.prompt_activation_readiness import build_prompt_activation_readiness


def test_prompt_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_prompt_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.prompt_store_mode == "memory"
    assert readiness.management_mode == "SEEDED_MEMORY"
    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 4
    assert len(readiness.activation_path) == 4
