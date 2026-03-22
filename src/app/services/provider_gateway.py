from __future__ import annotations

from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.stub_text_provider import StubTextProvider
from app.services.provider_policy import require_supported_text_generation_mode

_stub_text_provider = StubTextProvider()


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    # Foundation-phase gateway keeps provider selection explicit while live execution stays disabled.
    mode = require_supported_text_generation_mode()
    if mode.value == "disabled":
        return _stub_text_provider.execute(request)
    if mode.value == "stub":
        return _stub_text_provider.execute(request)
    return _stub_text_provider.execute(request)
