"""Typed accepted-output projection for `advisor_brief.pack@v1` runs (issue #162).

This contract publishes the exact reviewed narrative of one accepted run so an
owning consumer (Report/Gateway composition) can retrieve it immutably instead of
regenerating content, parsing previews, or reading internal storage references.
It is review-gated and NOT client-authoritative: lotus-ai proves what was
generated, reviewed and accepted; client-report suitability and distribution
remain the calling workflow's authority.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

ACCEPTED_OUTPUT_SCHEMA_ADVISOR_BRIEF_V1 = (
    "lotus-ai.workflow_pack_run.accepted_output.advisor_brief.v1"
)
ACCEPTED_OUTPUT_CONTENT_HASH_ALGORITHM = "sha256"


class AdvisorBriefAcceptedNarrativeItem(BaseModel):
    """One bounded narrative element (talking point or risk/exception)."""

    headline: str = Field(description="Short reviewed statement for this element.")
    detail: str = Field(description="Reviewed supporting detail for the headline.")
    tone: str = Field(description="Bounded tone marker recorded with the element.")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Source references grounding this element, as recorded at generation.",
    )


class AdvisorBriefAcceptedContextIdentity(BaseModel):
    """Bounded report-context identity for consumer-side matching.

    Carries exactly the context identifiers the accepted output was generated
    for. `as_of_date`, `reporting_currency` and `benchmark` are populated when
    the persisted output recorded them and are null otherwise - a consumer must
    treat a null as "not asserted by the source", never as a wildcard match.
    """

    portfolio_id: str = Field(description="Portfolio the accepted brief was generated for.")
    period: str = Field(description="Reporting period label the accepted brief covers.")
    as_of_date: str | None = Field(
        default=None,
        description="As-of date recorded with the output, when the source asserted one.",
    )
    reporting_currency: str | None = Field(
        default=None,
        description="Reporting currency recorded with the output, when asserted.",
    )
    benchmark: str | None = Field(
        default=None,
        description="Benchmark identity recorded with the output, when asserted.",
    )


class AdvisorBriefAcceptedReviewIdentity(BaseModel):
    """Who accepted the run and when, from the durable review event ledger."""

    reviewed_by: str = Field(description="Actor recorded on the accepting review transition.")
    reviewed_at: str = Field(description="Instant of the accepting review transition (UTC).")


class WorkflowPackRunAcceptedOutputResponse(BaseModel):
    """The exact accepted `advisor_brief.pack@v1` output for one run.

    Only completed, accepted, non-superseded runs backed by their intact
    governed output artifact return this response; every other posture fails
    closed with a bounded reason code. The response never contains prompts,
    arbitrary task payloads, object-store paths, storage references, provider
    secrets, or generic artifact bodies.
    """

    schema_id: str = Field(
        description="Versioned schema discriminator for this projection.",
    )
    service: str = Field(description="Publishing service identity.")
    version: str = Field(description="Publishing service version.")
    run_id: str = Field(description="Accepted workflow-pack run identity.")
    pack_id: str = Field(description="Workflow pack identity.")
    pack_family: str = Field(description="Workflow pack family.")
    pack_version: str = Field(description="Workflow pack version.")
    task_id: str = Field(description="Task identity that produced the output.")
    request_id: str = Field(description="Originating request identity.")
    tenant_id: str = Field(description="Tenant the run belongs to and was retrieved for.")
    workflow_authority_owner: str = Field(
        description="Service that owns consequence-bearing workflow authority for this pack.",
    )
    review: AdvisorBriefAcceptedReviewIdentity = Field(
        description="Accepting reviewer identity and time from the review event ledger.",
    )
    advisor_brief_status: str = Field(
        description="Bounded output status label recorded with the accepted brief.",
    )
    coverage_state: str = Field(
        description="Bounded source-coverage label recorded with the accepted brief.",
    )
    grounded_summary: str = Field(
        description="The exact reviewed summary narrative, unmodified since acceptance.",
    )
    talking_points: list[AdvisorBriefAcceptedNarrativeItem] = Field(
        description="Reviewed talking points, in recorded order.",
    )
    risks_and_exceptions: list[AdvisorBriefAcceptedNarrativeItem] = Field(
        description="Reviewed risks and exceptions, in recorded order.",
    )
    context: AdvisorBriefAcceptedContextIdentity = Field(
        description="Bounded report-context identity for consumer-side matching.",
    )
    source_refs: list[str] = Field(
        description="Source references the brief was grounded on, as recorded at generation.",
    )
    evidence_types: list[str] = Field(
        description="Evidence descriptor types recorded with the run, names only.",
    )
    content_hash: str = Field(
        description=(
            "Canonical hash over the published narrative and context fields; changes when "
            "any published field changes, so consumers can pin the exact accepted content."
        ),
    )
    content_hash_algorithm: str = Field(
        description="Algorithm of content_hash.",
    )
    notes: list[str] = Field(
        description="Boundary statements this projection ships with.",
    )
