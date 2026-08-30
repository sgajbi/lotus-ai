from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.base import TextGenerationProviderAdapter
from app.providers.openai_compatible_text_transport import (
    OPENAI_MANAGED_TEXT_DESCRIPTOR,
    execute_openai_compatible_text_request,
)


class OpenAILiveTextProvider(TextGenerationProviderAdapter):
    descriptor = OPENAI_MANAGED_TEXT_DESCRIPTOR

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        return execute_openai_compatible_text_request(
            descriptor=self.descriptor,
            request=request,
            api_base=settings.live_text_api_base,
            api_key=settings.live_text_provider_api_key,
            require_api_key=True,
        )
