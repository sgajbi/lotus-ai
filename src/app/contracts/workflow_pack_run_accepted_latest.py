"""Latest-accepted run lookup envelope for one pack family (issue #183).

This contract answers the pre-order availability question the report ordering
surface must answer truthfully - "does an accepted brief exist for this
portfolio and context?" - with a bounded IDENTITY envelope only. It carries no
narrative fields: the consumer fetches the narrative through the run_id-keyed
accepted-output projection, so there is exactly one narrative-bearing surface.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.workflow_pack_run_accepted_output import (
    AdvisorBriefAcceptedContextIdentity,
    AdvisorBriefAcceptedReviewIdentity,
)

ACCEPTED_LATEST_SCHEMA_V1 = "lotus-ai.workflow_pack_run.accepted_latest.v1"


class WorkflowPackRunAcceptedLatestResponse(BaseModel):
    """Identity of the latest accepted run of one pack family for one portfolio.

    "Latest" is deterministic: the run whose accepting review event is most
    recent among completed, accepted, non-superseded runs of the pack family
    whose accepted output asserts the requested portfolio (review-time ties
    break on run_id, descending). Optional context filters compare only
    against values the source asserted - an unasserted value never
    wildcard-matches a caller filter. The response never contains narrative,
    prompts, task payloads, object-store paths, storage references, provider
    secrets, or artifact bodies.
    """

    schema_id: str = Field(description="Versioned schema discriminator for this lookup envelope.")
    service: str = Field(description="Publishing service identity.")
    version: str = Field(description="Publishing service version.")
    run_id: str = Field(description="Latest accepted workflow-pack run identity.")
    pack_id: str = Field(description="Workflow pack identity.")
    pack_family: str = Field(description="Workflow pack family the lookup was scoped to.")
    pack_version: str = Field(description="Workflow pack version.")
    tenant_id: str = Field(description="Tenant the run belongs to and was retrieved for.")
    workflow_authority_owner: str = Field(
        description="Service that owns consequence-bearing workflow authority for this pack.",
    )
    context: AdvisorBriefAcceptedContextIdentity = Field(
        description="Bounded report-context identity the accepted output asserted.",
    )
    review: AdvisorBriefAcceptedReviewIdentity = Field(
        description="Accepting reviewer identity and time from the review event ledger.",
    )
    accepted_output_schema_id: str = Field(
        description=(
            "Schema of the run_id-keyed accepted-output projection the consumer must fetch "
            "for the narrative content."
        ),
    )
    content_hash: str = Field(
        description=(
            "Canonical hash of the accepted-output projection this envelope points at, so a "
            "consumer can pin the exact accepted content before and after fetching it."
        ),
    )
    content_hash_algorithm: str = Field(description="Algorithm of content_hash.")
    notes: list[str] = Field(description="Boundary statements this lookup ships with.")
