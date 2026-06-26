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
from app.providers.advisory_copilot_stub import build_advisory_copilot_stub_result
from app.providers.advisor_brief_stub import build_advisor_brief_stub_result
from app.providers.dpm_exception_summary_stub import build_dpm_exception_summary_stub_result
from app.providers.idea_explanation_stub import build_idea_explanation_stub_result
from app.providers.outcome_review_narrative_stub import (
    build_outcome_review_narrative_stub_result,
)
from app.providers.operations_handoff_summary_stub import (
    build_operations_handoff_summary_stub_result,
)
from app.providers.pm_quality_summary_stub import build_pm_quality_summary_stub_result
from app.providers.proposal_memo_commentary_stub import (
    build_proposal_memo_commentary_stub_result,
)
from app.providers.proof_pack_pm_memo_stub import build_proof_pack_pm_memo_stub_result
from app.providers.wave_pm_memo_stub import build_wave_pm_memo_stub_result


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
        idea_explanation_result = build_idea_explanation_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and idea_explanation_result:
            message, structured_output = idea_explanation_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed Idea explanation posture before "
                        "live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        advisory_copilot_result = build_advisory_copilot_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and advisory_copilot_result:
            message, structured_output = advisory_copilot_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed advisory copilot posture before "
                        "live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        proposal_memo_commentary_result = build_proposal_memo_commentary_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and proposal_memo_commentary_result:
            message, structured_output = proposal_memo_commentary_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed proposal memo commentary posture "
                        "before live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        pm_quality_summary_result = build_pm_quality_summary_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and pm_quality_summary_result:
            message, structured_output = pm_quality_summary_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed PM quality summary posture "
                        "before live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        dpm_exception_summary_result = build_dpm_exception_summary_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and dpm_exception_summary_result:
            message, structured_output = dpm_exception_summary_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed DPM exception summary posture "
                        "before live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        operations_handoff_summary_result = build_operations_handoff_summary_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and operations_handoff_summary_result:
            message, structured_output = operations_handoff_summary_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed operations handoff summary posture "
                        "before live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        wave_pm_memo_result = build_wave_pm_memo_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and wave_pm_memo_result:
            message, structured_output = wave_pm_memo_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed wave memo posture before live "
                        "provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        proof_pack_pm_memo_result = build_proof_pack_pm_memo_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and proof_pack_pm_memo_result:
            message, structured_output = proof_pack_pm_memo_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed proof-pack memo posture before "
                        "live provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        outcome_review_narrative_result = build_outcome_review_narrative_stub_result(
            context_payload=request.context_payload,
        )
        if request.task_id == "explain.v1" and outcome_review_narrative_result:
            message, structured_output = outcome_review_narrative_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "output_label": request.output_label,
                    "safety_mode": request.safety_mode,
                    "redaction_posture": request.redaction_posture,
                    "context_summary": request.context_summary,
                    "context_keys": sorted(request.context_payload.keys()),
                    "source_refs": request.source_refs,
                    "stub_reason": (
                        "lotus-ai emits deterministic governed narrative posture before live "
                        "provider rollout is enabled for this workflow pack."
                    ),
                },
            )
        advisor_brief_result = build_advisor_brief_stub_result(
            context_payload=request.context_payload,
            source_refs=request.source_refs,
        )
        if request.task_id == "explain.v1" and advisor_brief_result:
            message, structured_output = advisor_brief_result
            return ProviderExecutionResponse(
                provider_id=self.descriptor.provider_id,
                provider_mode=settings.provider_mode,
                adapter_kind=self.descriptor.adapter_kind,
                failure_category=None,
                timeout_ms=request.timeout_ms,
                retry_count=0,
                max_output_tokens=request.max_output_tokens,
                stubbed=True,
                message=message,
                structured_output={
                    **structured_output,
                    "phase": settings.delivery_phase,
                    "provider_id": self.descriptor.provider_id,
                    "provider_mode": settings.provider_mode,
                    "adapter_kind": self.descriptor.adapter_kind.value,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
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
        return ProviderExecutionResponse(
            provider_id=self.descriptor.provider_id,
            provider_mode=settings.provider_mode,
            adapter_kind=self.descriptor.adapter_kind,
            failure_category=None,
            timeout_ms=request.timeout_ms,
            retry_count=0,
            max_output_tokens=request.max_output_tokens,
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
                "timeout_ms": request.timeout_ms,
                "retry_count": 0,
                "max_output_tokens": request.max_output_tokens,
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
