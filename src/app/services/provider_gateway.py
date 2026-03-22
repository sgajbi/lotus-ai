from __future__ import annotations

from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.stub_text_provider import StubTextProvider

_stub_text_provider = StubTextProvider()


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    # Foundation-phase gateway keeps provider selection explicit while live execution stays disabled.
    return _stub_text_provider.execute(request)
