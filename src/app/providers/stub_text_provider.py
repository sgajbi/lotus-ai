from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse


class StubTextProvider:
    provider_id = "text.stub"

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        return ProviderExecutionResponse(
            provider_id=self.provider_id,
            provider_mode=settings.provider_mode,
            stubbed=True,
            message=(
                "Stub execution completed for foundation-phase task "
                f"{request.task_id} requested by {request.caller_app}."
            ),
            structured_output={
                "phase": settings.delivery_phase,
                "provider_id": self.provider_id,
                "provider_mode": settings.provider_mode,
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
