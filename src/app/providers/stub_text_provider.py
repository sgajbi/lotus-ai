from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
)
from app.providers.base import ProviderAdapterDescriptor


class StubTextProvider:
    descriptor = ProviderAdapterDescriptor(
        provider_id="text.stub",
        display_name="Foundation Stub Text Provider",
        capability=ProviderCapability.TEXT_GENERATION,
        adapter_kind=ProviderAdapterKind.STUB,
        runtime_mode=ProviderExecutionMode.STUB,
        enabled_for_execution=False,
        source_reference="app.providers.stub_text_provider",
        notes=(
            "Foundation-phase deterministic placeholder execution path used for contract "
            "validation and audit behavior."
        ),
    )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        return ProviderExecutionResponse(
            provider_id=self.descriptor.provider_id,
            provider_mode=settings.provider_mode,
            adapter_kind=self.descriptor.adapter_kind,
            stubbed=True,
            message=(
                "Stub execution completed for foundation-phase task "
                f"{request.task_id} requested by {request.caller_app}."
            ),
            structured_output={
                "phase": settings.delivery_phase,
                "provider_id": self.descriptor.provider_id,
                "provider_mode": settings.provider_mode,
                "adapter_kind": self.descriptor.adapter_kind.value,
                "output_label": request.output_label,
                "safety_mode": request.safety_mode,
                "redaction_posture": request.redaction_posture,
                "context_summary": request.context_summary,
                "context_keys": sorted(request.context_payload.keys()),
                "source_refs": request.source_refs,
                "stub_reason": (
                    "lotus-ai foundation phase exposes governed integration contracts "
                    "before live provider execution is enabled."
                ),
            },
        )
