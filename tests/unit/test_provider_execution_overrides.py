"""Execution-scoped provider overrides and hermetic enforcement (issue #148)."""

from concurrent.futures import ThreadPoolExecutor

from pytest import raises

from app.providers.openai_compatible_text_transport import post_openai_compatible_response
from app.providers.openai_live_embedding_provider import _post_openai_embedding
from app.services.local_openai_compatible_endpoint_probe import (
    LocalOpenAICompatibleEndpointStatus,
    build_local_openai_compatible_endpoint_status,
    reset_local_openai_compatible_endpoint_probe_cache,
)
from app.services.provider_execution_overrides import (
    get_local_probe_status_override,
    get_text_transport_post_override,
    hermetic_provider_execution,
    is_hermetic_provider_execution,
    override_local_probe_status,
    override_text_transport_post,
)


def _probe_status(*, reachable: bool = True) -> LocalOpenAICompatibleEndpointStatus:
    return LocalOpenAICompatibleEndpointStatus(
        endpoint_reachable=reachable,
        model_available=reachable,
        configured_model_id="qwen3:8b",
        blocking_reason=None if reachable else "Endpoint is not reachable.",
    )


def test_transport_override_applies_only_inside_the_installing_execution() -> None:
    fake_payload = {"id": "resp_override", "output_text": "OK"}

    with override_text_transport_post(lambda **_: fake_payload):
        assert get_text_transport_post_override() is not None
        # The override is contextvar-scoped: another thread (a concurrent
        # production request) must not observe it. This is the regression
        # test for the process-wide bleed that unittest.mock.patch caused.
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(get_text_transport_post_override).result() is None

        response = post_openai_compatible_response(
            api_base="https://api.openai.com/v1",
            api_key=None,
            payload={"model": "gpt-5.4"},
            timeout_seconds=1.0,
            serving_provider_id="text.openai",
            require_api_key=True,
            retry_limit=0,
        )
        assert response == fake_payload

    assert get_text_transport_post_override() is None


def test_hermetic_execution_blocks_text_transport_without_override() -> None:
    assert is_hermetic_provider_execution() is False
    with hermetic_provider_execution():
        assert is_hermetic_provider_execution() is True
        with raises(RuntimeError) as exc_info:
            post_openai_compatible_response(
                api_base="https://api.openai.com/v1",
                api_key="credential-ref:test",
                payload={"model": "gpt-5.4"},
                timeout_seconds=1.0,
                serving_provider_id="text.openai",
                require_api_key=True,
                retry_limit=0,
            )
        assert "post_openai_compatible_response" in str(exc_info.value)
        assert "never perform real provider I/O" in str(exc_info.value)
    assert is_hermetic_provider_execution() is False


def test_hermetic_execution_blocks_embedding_post() -> None:
    with hermetic_provider_execution():
        with raises(RuntimeError) as exc_info:
            _post_openai_embedding(
                api_base="https://api.openai.com/v1",
                api_key="credential-ref:test",
                payload={"model": "text-embedding-3-large", "input": ["text"]},
            )
    assert "_post_openai_embedding" in str(exc_info.value)


def test_hermetic_execution_blocks_local_probe_without_override() -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    with hermetic_provider_execution():
        with raises(RuntimeError) as exc_info:
            build_local_openai_compatible_endpoint_status()
    assert "build_local_openai_compatible_endpoint_status" in str(exc_info.value)


def test_probe_override_supplies_status_without_network() -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    status = _probe_status(reachable=True)
    with hermetic_provider_execution():
        with override_local_probe_status(status):
            assert build_local_openai_compatible_endpoint_status() is status
    assert get_local_probe_status_override() is None
