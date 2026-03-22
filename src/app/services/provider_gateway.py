from __future__ import annotations

from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.stub_text_provider import StubTextProvider
from app.services.provider_policy import require_supported_text_generation_mode

_stub_text_provider = StubTextProvider()


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    # Foundation-phase gateway validates configured mode but routes all supported execution
    # through the explicit stub provider until a governed live provider path exists.
    require_supported_text_generation_mode()
    return _stub_text_provider.execute(request)
