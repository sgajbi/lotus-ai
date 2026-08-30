"""Build the review-gated accepted-output projection for one workflow-pack run.

Issue #162: downstream Report/Gateway composition needs the exact accepted
`advisor_brief.pack@v1` narrative by `run_id`. This service joins the durable
run record, the review event ledger and the governed `run_output_summary`
artifact inside lotus-ai and fails closed on every posture that is not
"completed, accepted, not superseded, artifact intact".

Design decisions, deliberate:

- A pack-specific projection registry, so arbitrary future structured-output
  keys never become implicitly retrievable: a pack family earns retrieval only
  by shipping its own typed projector.
- Unknown run and wrong-tenant retrieval share one not-found shape - a run id
  must not become a cross-tenant existence oracle.
- The canonical content hash is computed from the published projection fields
  themselves (canonical JSON, sorted keys), so it changes exactly when any
  published narrative or context field changes and is reproducible by a
  consumer holding only the response.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from app.config import settings
from app.contracts.workflow_pack_run_accepted_output import (
    ACCEPTED_OUTPUT_CONTENT_HASH_ALGORITHM,
    ACCEPTED_OUTPUT_SCHEMA_ADVISOR_BRIEF_V1,
    AdvisorBriefAcceptedContextIdentity,
    AdvisorBriefAcceptedNarrativeItem,
    AdvisorBriefAcceptedReviewIdentity,
    WorkflowPackRunAcceptedOutputResponse,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from app.services.artifact_store import get_artifact_object_store
from app.services.workflow_pack_run_ledger import ensure_workflow_pack_run_store_ready
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_run_review_summary import (
    build_workflow_pack_run_review_summary,
)


class AcceptedOutputNotFoundError(LookupError):
    """Unknown run, or a run the caller's tenant may not see - one shape, no leak."""


class AcceptedOutputNotAvailableError(ValueError):
    """The run exists in the caller's tenant but its output must not be published."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


REASON_PACK_PROJECTION_UNSUPPORTED = "pack_projection_unsupported"
REASON_RUN_NOT_COMPLETED = "run_not_completed"
REASON_RUN_NOT_ACCEPTED = "run_not_accepted"
REASON_RUN_SUPERSEDED = "run_superseded"
REASON_OUTPUT_ARTIFACT_MISSING = "output_artifact_missing"
REASON_OUTPUT_ARTIFACT_MALFORMED = "output_artifact_malformed"

ACCEPTED_OUTPUT_REASON_CODES = frozenset(
    {
        REASON_PACK_PROJECTION_UNSUPPORTED,
        REASON_RUN_NOT_COMPLETED,
        REASON_RUN_NOT_ACCEPTED,
        REASON_RUN_SUPERSEDED,
        REASON_OUTPUT_ARTIFACT_MISSING,
        REASON_OUTPUT_ARTIFACT_MALFORMED,
    }
)

_ACCEPTED_OUTPUT_NOTES = [
    "This projection publishes the exact accepted output of one reviewed run; it does not "
    "certify client-report suitability, client distribution, or bank release.",
    "Only completed, accepted, non-superseded runs backed by their intact governed output "
    "artifact are retrievable; every other posture fails closed with a bounded reason code.",
    "Consequence-bearing workflow authority remains with the workflow authority owner; "
    "lotus-ai remains the AI run, review and evidence system of record.",
]


def build_workflow_pack_run_accepted_output(
    *,
    run_id: str,
    caller_tenant_id: str,
) -> WorkflowPackRunAcceptedOutputResponse:
    ensure_workflow_pack_run_store_ready()
    store = get_workflow_pack_run_store()
    record = store.get_run(run_id=run_id)
    if record is None:
        raise AcceptedOutputNotFoundError(run_id)
    if not record.tenant_id or record.tenant_id != caller_tenant_id:
        # Wrong tenant and tenantless runs are indistinguishable from absent runs:
        # a tenant-scoped projection must not leak cross-tenant existence, and a
        # run with no tenant binding has no tenant it may be published to.
        raise AcceptedOutputNotFoundError(run_id)

    projector = _PROJECTORS.get(f"{record.pack_id}@{record.pack_version}")
    if projector is None:
        raise AcceptedOutputNotAvailableError(
            REASON_PACK_PROJECTION_UNSUPPORTED,
            "No typed accepted-output projection exists for this pack and version.",
        )

    if record.runtime_state != WorkflowPackRunRuntimeState.COMPLETED.value:
        raise AcceptedOutputNotAvailableError(
            REASON_RUN_NOT_COMPLETED,
            "Accepted output is only published for completed runs.",
        )
    if record.review_state != WorkflowPackRunReviewState.ACCEPTED.value:
        raise AcceptedOutputNotAvailableError(
            REASON_RUN_NOT_ACCEPTED,
            "Accepted output is only published after a recorded ACCEPT review.",
        )
    if record.superseded_by_run_id:
        raise AcceptedOutputNotAvailableError(
            REASON_RUN_SUPERSEDED,
            "This run has been superseded; retrieve the superseding accepted run instead.",
        )

    payload = _load_intact_output_payload(record)
    review = _accepting_review_identity(store=store, run_id=run_id)
    return projector(record=record, payload=payload, review=review)


def _accepting_review_identity(*, store: Any, run_id: str) -> AdvisorBriefAcceptedReviewIdentity:
    summary = build_workflow_pack_run_review_summary(events=store.list_events(run_id=run_id))
    if not summary.latest_review_actor or not summary.latest_review_event_at:
        # An ACCEPTED state without a recorded review transition is a ledger
        # inconsistency; publishing content without reviewer identity would break
        # the human-oversight evidence this projection exists to carry.
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            "The accepted run has no recorded accepting review event.",
        )
    reviewed_by = summary.latest_review_actor
    # The event ledger namespaces review actors as `review:<actor>`; publish the
    # reviewer identity itself.
    if reviewed_by.startswith("review:"):
        reviewed_by = reviewed_by.removeprefix("review:")
    return AdvisorBriefAcceptedReviewIdentity(
        reviewed_by=reviewed_by,
        reviewed_at=summary.latest_review_event_at,
    )


def _load_intact_output_payload(record: WorkflowPackRunRecord) -> dict[str, Any]:
    summary_artifact = next(
        (
            artifact
            for artifact in record.artifact_refs
            if artifact.domain == "workflow_pack"
            and artifact.artifact_type == "run_output_summary"
            and artifact.storage_reference
        ),
        None,
    )
    if summary_artifact is None:
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MISSING,
            "The governed run-output artifact is not linked to this run.",
        )
    _, _, object_key = summary_artifact.storage_reference.partition("://")
    stored_object = get_artifact_object_store().get_object(object_key=object_key)
    if stored_object is None:
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MISSING,
            "The governed run-output artifact object is no longer retrievable.",
        )
    try:
        payload = json.loads(stored_object.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            "The governed run-output artifact could not be parsed.",
        ) from exc
    if not isinstance(payload, dict):
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            "The governed run-output artifact has an unexpected shape.",
        )
    if payload.get("run_id") != record.run_id or payload.get("pack_id") != record.pack_id:
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            "The governed run-output artifact does not match this run's identity.",
        )
    return payload


def _project_advisor_brief_v1(
    *,
    record: WorkflowPackRunRecord,
    payload: dict[str, Any],
    review: AdvisorBriefAcceptedReviewIdentity,
) -> WorkflowPackRunAcceptedOutputResponse:
    structured_output = payload.get("structured_output")
    if not isinstance(structured_output, dict):
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            "The accepted output does not carry a structured advisor brief.",
        )
    portfolio_id = _required_string(structured_output, "portfolio_id")
    period = _required_string(structured_output, "period")
    grounded_summary = _required_string(structured_output, "grounded_summary")
    advisor_brief_status = _required_string(structured_output, "advisor_brief_status")
    coverage_state = _required_string(structured_output, "coverage_state")

    context = AdvisorBriefAcceptedContextIdentity(
        portfolio_id=portfolio_id,
        period=period,
        as_of_date=_optional_string(structured_output, "as_of_date"),
        reporting_currency=_optional_string(structured_output, "reporting_currency"),
        benchmark=_optional_string(structured_output, "benchmark"),
    )
    talking_points = _narrative_items(structured_output.get("talking_points"))
    risks_and_exceptions = _narrative_items(structured_output.get("risks_and_exceptions"))
    source_refs = [ref for ref in payload.get("source_refs", []) if isinstance(ref, str)]
    evidence_types = [
        evidence for evidence in payload.get("evidence_types", []) if isinstance(evidence, str)
    ]

    hashed_content = {
        "schema_id": ACCEPTED_OUTPUT_SCHEMA_ADVISOR_BRIEF_V1,
        "run_id": record.run_id,
        "pack_id": record.pack_id,
        "pack_version": record.pack_version,
        "advisor_brief_status": advisor_brief_status,
        "coverage_state": coverage_state,
        "grounded_summary": grounded_summary,
        "talking_points": [item.model_dump() for item in talking_points],
        "risks_and_exceptions": [item.model_dump() for item in risks_and_exceptions],
        "context": context.model_dump(),
        "source_refs": source_refs,
    }
    content_hash = hashlib.sha256(
        json.dumps(hashed_content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return WorkflowPackRunAcceptedOutputResponse(
        schema_id=ACCEPTED_OUTPUT_SCHEMA_ADVISOR_BRIEF_V1,
        service=settings.service_name,
        version=settings.service_version,
        run_id=record.run_id,
        pack_id=record.pack_id,
        pack_family=record.pack_family,
        pack_version=record.pack_version,
        task_id=record.task_id,
        request_id=record.request_id,
        tenant_id=str(record.tenant_id),
        workflow_authority_owner=record.workflow_authority_owner,
        review=review,
        advisor_brief_status=advisor_brief_status,
        coverage_state=coverage_state,
        grounded_summary=grounded_summary,
        talking_points=talking_points,
        risks_and_exceptions=risks_and_exceptions,
        context=context,
        source_refs=source_refs,
        evidence_types=evidence_types,
        content_hash=content_hash,
        content_hash_algorithm=ACCEPTED_OUTPUT_CONTENT_HASH_ALGORITHM,
        notes=list(_ACCEPTED_OUTPUT_NOTES),
    )


def _narrative_items(raw: Any) -> list[AdvisorBriefAcceptedNarrativeItem]:
    if not isinstance(raw, list):
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            "The accepted output narrative elements have an unexpected shape.",
        )
    items: list[AdvisorBriefAcceptedNarrativeItem] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise AcceptedOutputNotAvailableError(
                REASON_OUTPUT_ARTIFACT_MALFORMED,
                "The accepted output narrative elements have an unexpected shape.",
            )
        items.append(
            AdvisorBriefAcceptedNarrativeItem(
                headline=_required_string(entry, "headline"),
                detail=_required_string(entry, "detail"),
                tone=_required_string(entry, "tone"),
                evidence_refs=[
                    ref for ref in entry.get("evidence_refs", []) if isinstance(ref, str)
                ],
            )
        )
    return items


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AcceptedOutputNotAvailableError(
            REASON_OUTPUT_ARTIFACT_MALFORMED,
            f"The accepted output is missing the required field '{key}'.",
        )
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


_ProjectorCallable = Callable[..., WorkflowPackRunAcceptedOutputResponse]

# A pack family earns accepted-output retrieval only by shipping a typed projector
# here; arbitrary structured-output keys are never implicitly retrievable.
_PROJECTORS: dict[str, _ProjectorCallable] = {
    "advisor_brief.pack@v1": _project_advisor_brief_v1,
}
