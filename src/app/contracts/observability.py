from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ObservabilityPosture(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ObservabilityFreshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class ObservabilityDomainId(str, Enum):
    PROVIDER = "provider"
    RETRIEVAL = "retrieval"
    ASYNC = "async"
    EVALUATION = "evaluation"
    PROMPT = "prompt"
    SAFETY = "safety"


class ObservabilityBreakdownSupport(BaseModel):
    caller_app_supported: bool = Field(
        description="Whether bounded caller-app summaries are supported for the domain."
    )
    tenant_supported: bool = Field(
        description="Whether bounded tenant summaries are supported for the domain."
    )
    capability_supported: bool = Field(
        description="Whether bounded capability/task/source summaries are supported for the domain."
    )


class DomainTelemetrySummary(BaseModel):
    domain_id: ObservabilityDomainId = Field(
        description="Stable platform domain represented by the telemetry summary."
    )
    posture: ObservabilityPosture = Field(
        description="Current observability posture for the domain."
    )
    freshness: ObservabilityFreshness = Field(
        description="Freshness posture for the bounded telemetry summary."
    )
    telemetry_sources: list[str] = Field(
        description="Bounded list of runtime or durable sources used to assemble the summary."
    )
    incident_evidence_supported: bool = Field(
        description="Whether the domain already has bounded incident-evidence support in the observability layer."
    )
    incident_signal_count: int = Field(
        description="Number of bounded incident signals currently surfaced for the domain."
    )
    breakdown_support: ObservabilityBreakdownSupport = Field(
        description="Caller, tenant, and capability breakdown support for the domain."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing explanation of the current telemetry posture."
    )


class IncidentEvidenceSummaryItem(BaseModel):
    domain_id: ObservabilityDomainId = Field(
        description="Stable domain owning the incident-evidence item."
    )
    evidence_id: str = Field(description="Stable incident-evidence identifier.")
    posture: ObservabilityPosture = Field(
        description="Current posture for the bounded incident-evidence item."
    )
    freshness: ObservabilityFreshness = Field(
        description="Freshness posture for the incident-evidence item."
    )
    durable: bool = Field(
        description="Whether the evidence item is assembled from durable state rather than volatile-only telemetry."
    )
    summary: str = Field(description="Human-readable explanation of the incident-evidence item.")


class ObservabilityRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the observability runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    posture: ObservabilityPosture = Field(
        description="Current overall observability posture for lotus-ai."
    )
    freshness: ObservabilityFreshness = Field(
        description="Current overall freshness posture for the observability layer."
    )
    domain_count: int = Field(description="Number of observability domains summarized in this response.")
    healthy_domain_count: int = Field(
        description="Number of summarized domains currently reporting healthy observability posture."
    )
    degraded_domain_count: int = Field(
        description="Number of summarized domains currently reporting degraded observability posture."
    )
    unavailable_domain_count: int = Field(
        description="Number of summarized domains currently reporting unavailable observability posture."
    )
    incident_evidence_supported_domain_count: int = Field(
        description="Number of summarized domains already carrying bounded incident-evidence support."
    )
    domains: list[DomainTelemetrySummary] = Field(
        description="Bounded per-domain telemetry summaries for the current observability layer."
    )
    incident_evidence_items: list[IncidentEvidenceSummaryItem] = Field(
        description="Bounded incident-evidence items currently exposed by the observability layer."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current observability layer posture."
    )
