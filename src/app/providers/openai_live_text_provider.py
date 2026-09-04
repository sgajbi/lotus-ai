from __future__ import annotations

from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.providers.base import TextGenerationProviderAdapter
from app.providers.openai_compatible_text_transport import (
    OPENAI_MANAGED_TEXT_DESCRIPTOR,
    execute_openai_compatible_text_request,
)
from app.services.provider_execution_config import ProviderExecutionConfig


class OpenAILiveTextProvider(TextGenerationProviderAdapter):
    descriptor = OPENAI_MANAGED_TEXT_DESCRIPTOR

    def execute(
        self, request: ProviderExecutionRequest, *, config: ProviderExecutionConfig
    ) -> ProviderExecutionResponse:
        return execute_openai_compatible_text_request(
            descriptor=self.descriptor,
            request=request,
            api_base=config.api_base,
            api_key=config.api_key,
            require_api_key=True,
            model_id=config.model_id,
            model_version=config.model_version,
            provider_id=config.provider_id,
            deployment=config.deployment,
        )
