"""Resolve the latest accepted run of one pack family for one portfolio.

Issue #183: the report ordering surface must truthfully answer "does an
accepted brief exist for this portfolio and context?" before an order is
placed. The accepted-output projection is run_id-keyed by design; this lookup
resolves the run_id and returns an identity envelope only - the narrative
stays on the single run_id-keyed surface.

Design decisions, deliberate:

- "Latest" is ordered by ACCEPTING-REVIEW recency (ties break on run_id,
  descending), not by run creation time: what governs staleness for a
  consumer is when a human accepted content, not when generation started.
- The lookup fails closed on ANY unresolvable candidate: a candidate whose
  review identity, pack projection, or governed output artifact cannot be
  resolved has an unknowable position in the "latest" order, so answering
  around it could present stale commentary as current. Corrupt accepted
  ledgers are an operations problem, never something to silently skip.
- Optional context filters compare only against values the source asserted:
  an unasserted as_of_date or reporting_currency never wildcard-matches a
  caller filter, so a filtered "ready" answer is always a proven match.
- Unknown tenants and unknown portfolios produce the same `no_accepted_run`
  not-found reason - this route must not become an existence oracle.
- The candidate scan is bounded and saturation fails closed: a truncated scan
  cannot prove which run is latest, so it refuses instead of guessing.
"""

from __future__ import annotations

from app.config import settings
from app.contracts.workflow_pack_run_accepted_latest import (
    ACCEPTED_LATEST_SCHEMA_V1,
    WorkflowPackRunAcceptedLatestResponse,
)
from app.contracts.workflow_pack_run_accepted_output import (
    WorkflowPackRunAcceptedOutputResponse,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunRecord,
    WorkflowPackRunRepository,
)
from app.services.workflow_pack_run_accepted_output import (
    REASON_OUTPUT_ARTIFACT_MALFORMED,
    REASON_PACK_PROJECTION_UNSUPPORTED,
    AcceptedOutputNotAvailableError,
    build_workflow_pack_run_accepted_output,
)
from app.services.workflow_pack_run_ledger import ensure_workflow_pack_run_store_ready
from app.services.workflow_pack_run_review_summary import (
    build_workflow_pack_run_review_summary,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store

REASON_NO_ACCEPTED_RUN = "no_accepted_run"
REASON_NO_CONTEXT_MATCH = "no_context_match"
REASON_LOOKUP_SCAN_SATURATED = "lookup_scan_saturated"

ACCEPTED_LATEST_NOT_FOUND_REASON_CODES = frozenset(
    {REASON_NO_ACCEPTED_RUN, REASON_NO_CONTEXT_MATCH}
)

# Pack families that may be discovered through this lookup: a family earns
# discovery exactly when it ships a typed accepted-output projection, so the
# lookup can never point at a run whose narrative is unretrievable.
_SUPPORTED_PACK_FAMILIES = frozenset({"advisor_brief"})

# Deliberate scan bound. One tenant's accepted, completed runs of one pack
# family is a small governed set; if it ever saturates this bound the lookup
# refuses (lookup_scan_saturated) rather than answering from a truncated scan.
_CANDIDATE_SCAN_LIMIT = 1000

_ACCEPTED_LATEST_NOTES = [
    "This envelope identifies the latest accepted run for the requested portfolio and "
    "context; it carries no narrative. Fetch the accepted-output projection by run_id "
    "for the reviewed content.",
    "A filtered match compares only against context values the source asserted; an "
    "unasserted value never satisfies a caller filter.",
    "Consequence-bearing workflow authority remains with the workflow authority owner; "
    "lotus-ai remains the AI run, review and evidence system of record.",
]


class AcceptedLatestNotFoundError(LookupError):
    """No accepted run answers the lookup - bounded reason, no existence leak."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def build_workflow_pack_run_accepted_latest(
    *,
    pack_family: str,
    portfolio_id: str,
    caller_tenant_id: str,
    as_of_date: str | None = None,
    reporting_currency: str | None = None,
) -> WorkflowPackRunAcceptedLatestResponse:
    if pack_family not in _SUPPORTED_PACK_FAMILIES:
        raise AcceptedOutputNotAvailableError(
            REASON_PACK_PROJECTION_UNSUPPORTED,
            "No typed accepted-output projection exists for this pack family.",
        )

    ensure_workflow_pack_run_store_ready()
    store = get_workflow_pack_run_store()
    candidates = [
        record
        for record in store.query_runs(
            tenant_id=caller_tenant_id,
            pack_family=pack_family,
            runtime_state=WorkflowPackRunRuntimeState.COMPLETED.value,
            review_state=WorkflowPackRunReviewState.ACCEPTED.value,
            limit=_CANDIDATE_SCAN_LIMIT,
        )
        if not record.superseded_by_run_id
    ]
    if len(candidates) >= _CANDIDATE_SCAN_LIMIT:
        raise AcceptedOutputNotAvailableError(
            REASON_LOOKUP_SCAN_SATURATED,
            "The candidate scan bound was reached; a truncated scan cannot prove which "
            "accepted run is latest.",
        )

    portfolio_asserted = False
    for record in _by_accepting_review_recency(store=store, candidates=candidates):
        projection = _resolve_candidate(record=record, caller_tenant_id=caller_tenant_id)
        if projection.context.portfolio_id != portfolio_id:
            continue
        portfolio_asserted = True
        if as_of_date is not None and projection.context.as_of_date != as_of_date:
            continue
        if (
            reporting_currency is not None
            and projection.context.reporting_currency != reporting_currency
        ):
            continue
        return _envelope(projection=projection, pack_family=pack_family)

    if portfolio_asserted:
        raise AcceptedLatestNotFoundError(
            REASON_NO_CONTEXT_MATCH,
            "Accepted runs exist for this portfolio, but none assert the requested "
            "context filters.",
        )
    raise AcceptedLatestNotFoundError(
        REASON_NO_ACCEPTED_RUN,
        "No accepted run of this pack family asserts the requested portfolio.",
    )


def _by_accepting_review_recency(
    *,
    store: WorkflowPackRunRepository,
    candidates: list[WorkflowPackRunRecord],
) -> list[WorkflowPackRunRecord]:
    """Order candidates newest-accepting-review first, run_id breaking ties.

    An ACCEPTED run without a recorded review transition has an unknowable
    position in this order; it fails the whole lookup closed rather than being
    silently skipped past.
    """

    keyed: list[tuple[str, str, WorkflowPackRunRecord]] = []
    for record in candidates:
        summary = build_workflow_pack_run_review_summary(
            events=store.list_events(run_id=record.run_id)
        )
        if not summary.latest_review_event_at:
            raise AcceptedOutputNotAvailableError(
                REASON_OUTPUT_ARTIFACT_MALFORMED,
                "An accepted candidate run has no recorded accepting review event, so "
                "the latest-accepted order cannot be proven.",
            )
        keyed.append((summary.latest_review_event_at, record.run_id, record))
    keyed.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [record for _, _, record in keyed]


def _resolve_candidate(
    *,
    record: WorkflowPackRunRecord,
    caller_tenant_id: str,
) -> WorkflowPackRunAcceptedOutputResponse:
    """Resolve one candidate through the run_id projection - one code path
    computes context, review identity and content hash for both surfaces.

    Every projection failure (unsupported version, missing or malformed
    artifact) propagates: an unresolvable candidate makes "latest for this
    portfolio" unanswerable, because its context - and therefore its claim to
    being the answer - cannot be proven.
    """

    return build_workflow_pack_run_accepted_output(
        run_id=record.run_id,
        caller_tenant_id=caller_tenant_id,
    )


def _envelope(
    *,
    projection: WorkflowPackRunAcceptedOutputResponse,
    pack_family: str,
) -> WorkflowPackRunAcceptedLatestResponse:
    return WorkflowPackRunAcceptedLatestResponse(
        schema_id=ACCEPTED_LATEST_SCHEMA_V1,
        service=settings.service_name,
        version=settings.service_version,
        run_id=projection.run_id,
        pack_id=projection.pack_id,
        pack_family=pack_family,
        pack_version=projection.pack_version,
        tenant_id=projection.tenant_id,
        workflow_authority_owner=projection.workflow_authority_owner,
        context=projection.context,
        review=projection.review,
        accepted_output_schema_id=projection.schema_id,
        content_hash=projection.content_hash,
        content_hash_algorithm=projection.content_hash_algorithm,
        notes=list(_ACCEPTED_LATEST_NOTES),
    )
