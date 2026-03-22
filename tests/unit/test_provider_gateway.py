from app.contracts.providers import ProviderExecutionRequest
from app.services.provider_gateway import execute_text_generation


def test_execute_text_generation_routes_through_stub_provider() -> None:
    response = execute_text_generation(
        ProviderExecutionRequest(
            task_id="explain.v1",
            caller_app="lotus-manage",
            prompt_version="foundation.explain.v1",
            context_summary="Explain rebalance outcome",
            context_payload={"status": "BLOCKED", "rule_count": 3},
            source_refs=["lotus-manage:run:reb_001"],
        )
    )

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "disabled"
    assert response.stubbed is True
    assert response.structured_output["provider_id"] == "text.stub"
    assert response.structured_output["context_keys"] == ["rule_count", "status"]
