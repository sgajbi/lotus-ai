from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResiliencePosture(str, Enum):
    LOCAL_OR_DEMO_CONTINUITY = "LOCAL_OR_DEMO_CONTINUITY"
    PARTIAL_RUNTIME_DURABILITY = "PARTIAL_RUNTIME_DURABILITY"
    INVENTORIED_PROD_SHAPED = "INVENTORIED_PROD_SHAPED"


class ResilienceDeliveryStage(str, Enum):
    INVENTORIED_ONLY = "INVENTORIED_ONLY"
    ORDERED_RECOVERY_READY = "ORDERED_RECOVERY_READY"
    DRILL_VERIFIED = "DRILL_VERIFIED"


class ResilienceDependencyKind(str, Enum):
    AUTHORITATIVE_STORE = "AUTHORITATIVE_STORE"
    RUNTIME_DEPENDENCY = "RUNTIME_DEPENDENCY"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"


class ResilienceRecoveryClassification(str, Enum):
    RUNTIME_RECOVERABLE = "RUNTIME_RECOVERABLE"
    DOCUMENTED_FALLBACK = "DOCUMENTED_FALLBACK"
    EXTERNAL_RECOVERY_REQUIRED = "EXTERNAL_RECOVERY_REQUIRED"
    BLOCKED = "BLOCKED"


class ResilienceRestoreClassification(str, Enum):
    PLATFORM_METADATA_RESTORE = "PLATFORM_METADATA_RESTORE"
    PLATFORM_RUNTIME_RECONCILIATION = "PLATFORM_RUNTIME_RECONCILIATION"
    EXTERNAL_DEPENDENCY_VALIDATION = "EXTERNAL_DEPENDENCY_VALIDATION"


class ResilienceRecoveryState(str, Enum):
    STEADY = "STEADY"
    DEGRADED = "DEGRADED"
    RESTORED_WITH_FINDINGS = "RESTORED_WITH_FINDINGS"


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
    recovery_state: ResilienceRecoveryState = Field(
        description="Current operator-facing degraded-versus-restored runtime posture for this dependency."
    )
    recovery_findings: list[str] = Field(
        default_factory=list,
        description="Human-readable recovery findings that explain degraded or restored-with-findings posture for this dependency.",
    )
    detail: str = Field(description="Human-readable explanation of the current resilience posture.")


class ResilienceRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the resilience runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_stage: ResilienceDeliveryStage = Field(
        description="Current RFC-0017 delivery stage implemented in lotus-ai."
    )
    recovery_state: ResilienceRecoveryState = Field(
        description="Current top-level degraded-versus-restored runtime posture across critical continuity dependencies."
    )
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
    recovery_attention_dependency_count: int = Field(
        description="Number of dependencies currently reporting degraded or restored-with-findings runtime posture."
    )
    recovery_findings: list[str] = Field(
        description="Top-level recovery findings requiring operator review before continuity can be treated as steady."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable resilience findings showing where continuity still depends on fallback or external recovery assumptions."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current resilience posture."
    )


class ResilienceRestoreStepDescriptor(BaseModel):
    step_id: str = Field(description="Stable restore-plan step identifier.")
    sequence: int = Field(description="1-based restore ordering position.")
    classification: ResilienceRestoreClassification = Field(
        description="Whether the step restores platform metadata, reconciles runtime state, or validates an external dependency."
    )
    dependency_ids: list[str] = Field(
        description="Resilience dependency identifiers owned by this restore step."
    )
    requires_completed_steps: list[str] = Field(
        description="Restore steps that must complete before this step should start."
    )
    restore_action_summary: str = Field(
        description="Human-readable summary of the bounded restore or reconciliation action."
    )
    success_criteria: list[str] = Field(
        description="Checks operators should use to treat this step as successfully restored."
    )
    rollback_boundary: str = Field(
        description="Short explanation distinguishing restore of durable state from functional rollback at this step."
    )


class ResilienceRestorePlanResponse(BaseModel):
    service: str = Field(description="Service name emitting the resilience restore plan.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_stage: ResilienceDeliveryStage = Field(
        description="Current RFC-0017 delivery stage implemented in lotus-ai."
    )
    restore_step_count: int = Field(description="Number of ordered restore steps in the plan.")
    restore_steps: list[ResilienceRestoreStepDescriptor] = Field(
        description="Ordered restore and recovery descriptors for authoritative stores and critical dependencies."
    )
    restore_validation_summary: list[str] = Field(
        description="High-level restore validation expectations that apply across the plan."
    )
    status_summary: list[str] = Field(
        description="Operator-facing summary of what this restore plan does and does not claim."
    )
