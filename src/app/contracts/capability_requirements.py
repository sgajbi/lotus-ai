"""Capability requirements: what a workload needs, never which vendor feature (issue #244, S1).

A consuming Lotus application already cannot name a provider or model — no
request contract exposes one. What it could not do until now is state
*requirements*: the workload needs structured output, must answer within a
latency ceiling, must not exceed a governed cost. This module is that
vocabulary, deliberately provider-neutral so it survives provider churn:
``structured_output_required``, never ``openai_json_mode``; ``max_latency_ms``,
never ``use_fast_model``.

Slice 1 is the contract only. Declared requirements are validated and recorded
as execution evidence with an explicit ``NOT_ENFORCED`` posture — never
silently ignored, because a consumer who declares a ceiling must be able to
see whether anything is holding it. Slice 3 makes them an eligibility filter
in the existing routing decision and flips the posture.

Dimensions ship only when they have a concrete enforcement story against
catalogue facts provable from current evidence. Residency, data
classification, workload criticality and modality are deliberately absent: no
governed vocabulary for them exists in the platform yet, and inventing one
here would park dead, unenforceable fields on every request.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The slice-1 posture: requirements are recorded, visible, and not yet an
# eligibility filter. Slice 3 introduces the enforced posture alongside the
# filter itself; this constant is the only value that exists until then.
REQUIREMENTS_NOT_ENFORCED = "NOT_ENFORCED"


class CapabilityRequirements(BaseModel):
    """Workload requirements declared alongside a task request.

    Every field is optional; at least one must be set — an empty requirements
    object is a statement that means nothing, and recording it as evidence
    would be noise wearing a contract's clothes.
    """

    model_config = ConfigDict(frozen=True)

    structured_output_required: bool | None = Field(
        default=None,
        description=(
            "The workload requires machine-parseable structured output (the Lotus "
            "capability, not any vendor's JSON mode)."
        ),
    )
    tool_calling_required: bool | None = Field(
        default=None,
        description="The workload requires model-initiated tool calling.",
    )
    max_latency_ms: int | None = Field(
        default=None,
        ge=100,
        le=600_000,
        description="Latency ceiling for the serving execution, in milliseconds.",
    )
    max_estimated_cost_usd: float | None = Field(
        default=None,
        gt=0,
        le=1_000,
        description=(
            "Ceiling on the governed cost estimate for one execution, in the same "
            "estimate currency as `estimated_cost_usd` on the response."
        ),
    )

    @model_validator(mode="after")
    def _at_least_one_dimension(self) -> CapabilityRequirements:
        if all(getattr(self, field) is None for field in CapabilityRequirements.model_fields):
            raise ValueError(
                "capability requirements must state at least one dimension; omit the "
                "requirements object entirely when the workload has none"
            )
        return self

    def declared_dimensions(self) -> dict[str, bool | int | float]:
        """The dimensions actually stated, for evidence recording."""

        return {
            field: value
            for field in CapabilityRequirements.model_fields
            if (value := getattr(self, field)) is not None
        }
