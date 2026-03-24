from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResiliencePosture(str, Enum):
    LOCAL_OR_DEMO_CONTINUITY = "LOCAL_OR_DEMO_CONTINUITY"
    PARTIAL_RUNTIME_DURABILITY = "PARTIAL_RUNTIME_DURABILITY"
    INVENTORIED_PROD_SHAPED = "INVENTORIED_PROD_SHAPED"


class ResilienceDependencyKind(str, Enum):
    AUTHORITATIVE_STORE = "AUTHORITATIVE_STORE"
    RUNTIME_DEPENDENCY = "RUNTIME_DEPENDENCY"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"


class ResilienceRecoveryClassification(str, Enum):
    RUNTIME_RECOVERABLE = "RUNTIME_RECOVERABLE"
    DOCUMENTED_FALLBACK = "DOCUMENTED_FALLBACK"
    EXTERNAL_RECOVERY_REQUIRED = "EXTERNAL_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


class ResilienceDependencyDescriptor(BaseModel):
    dependency_id: str = Field(description="Stable resilience inventory identifier.")
    kind: ResilienceDependencyKind = Field(
        description="Whether the dependency is an authoritative store, a runtime dependency, or an external dependency."
    )
    authoritative: bool = Field(
        description="Whether this dependency holds or mediates authoritative platform truth."
    )
    recovery_classification: ResilienceRecoveryClassification = Field(
        description="Current bounded recovery classification for this dependency."
    )
    configured_mode: str = Field(
        description="Configured mode or backend label currently selected for this dependency."
    )
    restart_survivable: bool = Field(
        description="Whether this dependency currently preserves platform truth across process restart."
    )
    detail: str = Field(description="Human-readable explanation of the current resilience posture.")


class ResilienceRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the resilience runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    posture: ResiliencePosture = Field(
        description="Current top-level resilience inventory posture for lotus-ai."
    )
    dependency_count: int = Field(
        description="Number of resilience dependency descriptors included in this response."
    )
    authoritative_dependency_count: int = Field(
        description="Number of dependencies currently treated as authoritative platform truth."
    )
    restart_survivable_dependency_count: int = Field(
        description="Number of inventoried dependencies that currently preserve platform truth across restart."
    )
    dependencies: list[ResilienceDependencyDescriptor] = Field(
        description="Bounded resilience inventory covering authoritative stores and platform-critical dependencies."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable resilience findings showing where continuity still depends on fallback or external recovery assumptions."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current resilience posture."
    )
