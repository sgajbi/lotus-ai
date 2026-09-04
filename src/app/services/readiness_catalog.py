"""Readiness as data (issue #154, S1).

Ten near-identical runbook-readiness modules carried their operational
posture as hard-coded ``status="READY"`` literals - forty-odd endpoint
values that could not change when operational reality changed. This module
replaces them with one catalog
(``contracts/readiness/runbook_readiness_catalog.json``) and one builder:

- every item declares an ``execution_state`` in ``{ENFORCED, PARTIAL,
  DOCUMENTED_ONLY, OUT_OF_SCOPE, MISSING}``; a state not computed from
  runtime evidence is ``DOCUMENTED_ONLY``, never ``READY`` - the API now
  says what is actually true;
- ``runbook_ready`` is derived (every required item ``ENFORCED``), never
  asserted;
- the per-domain response contracts are unchanged in shape, so consumers
  keep parsing what they parsed before - only the honesty of the values
  changed.

Issue #284 (slice 1) folds in the three remaining declared runbook
domains - async, provider, and production go-live. Two of their values are
genuinely derived, and the catalog says so per ITEM rather than per module:
an item may name a ``computed_status`` or ``computed_note_suffix`` hook from
the bounded registries below, and the builder resolves it at request time -
declared posture stays data, derived posture stays computed, and an unknown
hook reference refuses at load. ``MISSING`` joins the state vocabulary for a
control that does not exist even on paper (the old ``NOT_READY`` literals):
calling an absent runbook ``DOCUMENTED_ONLY`` would claim a document that
was never written.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from typing import TypeVar

from pydantic import BaseModel

from app.config import settings
from app.contracts.access_control import (
    AccessControlRunbookReadinessItem,
    AccessControlRunbookReadinessResponse,
)
from app.contracts.async_runtime import (
    AsyncRunbookReadinessItem,
    AsyncRunbookReadinessResponse,
)
from app.contracts.artifacts import (
    ArtifactRunbookReadinessItem,
    ArtifactRunbookReadinessResponse,
)
from app.contracts.deployment_split import (
    DeploymentSplitRunbookReadinessItem,
    DeploymentSplitRunbookReadinessResponse,
)
from app.contracts.observability import (
    ObservabilityRunbookReadinessItem,
    ObservabilityRunbookReadinessResponse,
)
from app.contracts.production_baseline import (
    ProductionBaselineRunbookReadinessItem,
    ProductionBaselineRunbookReadinessResponse,
)
from app.contracts.production_go_live import (
    ProductionGoLiveRunbookReadinessItem,
    ProductionGoLiveRunbookReadinessResponse,
)
from app.contracts.providers import (
    ProviderRunbookReadinessItem,
    ProviderRunbookReadinessResponse,
)
from app.contracts.prompts import (
    PromptRunbookReadinessItem,
    PromptRunbookReadinessResponse,
)
from app.contracts.resilience import (
    ResilienceRunbookReadinessItem,
    ResilienceRunbookReadinessResponse,
)
from app.contracts.retrieval import (
    RetrievalRunbookReadinessItem,
    RetrievalRunbookReadinessResponse,
)
from app.contracts.safety import (
    SafetyRunbookReadinessItem,
    SafetyRunbookReadinessResponse,
)
from app.contracts.use_cases import (
    FirstUseCaseRunbookReadinessItem,
    FirstUseCaseRunbookReadinessResponse,
)

_CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "readiness"
    / "runbook_readiness_catalog.json"
)

EXECUTION_STATES = frozenset({"ENFORCED", "PARTIAL", "DOCUMENTED_ONLY", "OUT_OF_SCOPE", "MISSING"})

_FIRST_USE_CASE_ID = "lotus_performance.analytics_commentary.v1"
_FIRST_USE_CASE_CALLER_APP = "lotus-performance"


class CatalogRunbookItem(BaseModel):
    item_id: str
    execution_state: str
    required_for_activation: bool
    notes: str
    # Per-item derivation markers (issue #284): a non-null value names a hook
    # in the bounded registries below, and the builder resolves it at request
    # time. This is the catalog's `computed` marker - per item, because a
    # module can mix declared and derived values.
    computed_status: str | None = None
    computed_note_suffix: str | None = None


def _provider_rollout_posture_note_suffix() -> str:
    from app.services.provider_rollout_posture import build_provider_rollout_posture

    return build_provider_rollout_posture().notes


def _provider_runbook_alignment_status() -> str:
    """Go-live's provider alignment derives from the provider runbook surface:
    enforced only when every required provider runbook item is enforced,
    partial otherwise - the notes carry the dependency."""

    return "ENFORCED" if build_provider_runbook_readiness().runbook_ready else "PARTIAL"


COMPUTED_STATUS_HOOKS = {
    "provider_runbook_alignment": _provider_runbook_alignment_status,
}
COMPUTED_NOTE_SUFFIX_HOOKS = {
    "provider_rollout_posture": _provider_rollout_posture_note_suffix,
}


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, list[CatalogRunbookItem]]:
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    catalog: dict[str, list[CatalogRunbookItem]] = {}
    for domain, entry in raw.items():
        items = [CatalogRunbookItem.model_validate(item) for item in entry["items"]]
        for item in items:
            if item.execution_state not in EXECUTION_STATES:
                raise ValueError(
                    f"runbook readiness catalog: unknown execution_state "
                    f"'{item.execution_state}' on {domain}/{item.item_id}"
                )
            if (
                item.computed_status is not None
                and item.computed_status not in COMPUTED_STATUS_HOOKS
            ):
                raise ValueError(
                    f"runbook readiness catalog: unknown computed_status hook "
                    f"'{item.computed_status}' on {domain}/{item.item_id}"
                )
            if (
                item.computed_note_suffix is not None
                and item.computed_note_suffix not in COMPUTED_NOTE_SUFFIX_HOOKS
            ):
                raise ValueError(
                    f"runbook readiness catalog: unknown computed_note_suffix hook "
                    f"'{item.computed_note_suffix}' on {domain}/{item.item_id}"
                )
        catalog[domain] = items
    return catalog


def reset_readiness_catalog_cache() -> None:
    _load_catalog.cache_clear()


def catalog_runbook_items(domain: str) -> list[CatalogRunbookItem]:
    catalog = _load_catalog()
    if domain not in catalog:
        raise ValueError(f"runbook readiness catalog has no domain '{domain}'")
    return list(catalog[domain])


def _resolve(item: CatalogRunbookItem) -> tuple[str, str]:
    """One item's effective (status, notes): declared from the catalog, or
    derived through its named hook at request time."""

    status = (
        COMPUTED_STATUS_HOOKS[item.computed_status]()
        if item.computed_status is not None
        else item.execution_state
    )
    notes = item.notes
    if item.computed_note_suffix is not None:
        notes = f"{notes} {COMPUTED_NOTE_SUFFIX_HOOKS[item.computed_note_suffix]()}"
    return status, notes


def _summarize(resolved: list[tuple[CatalogRunbookItem, str]]) -> tuple[int, int, bool]:
    required = [status for item, status in resolved if item.required_for_activation]
    enforced = [status for status in required if status == "ENFORCED"]
    return len(required), len(enforced), bool(required) and len(enforced) == len(required)


_TResponse = TypeVar("_TResponse", bound=BaseModel)


def _build(
    domain: str, item_cls: type[BaseModel], response_cls: type[_TResponse], **extra: object
) -> _TResponse:
    items = catalog_runbook_items(domain)
    resolved = [(item, *_resolve(item)) for item in items]
    required_count, completed_count, ready = _summarize(
        [(item, status) for item, status, _ in resolved]
    )
    return response_cls(
        service=settings.service_name,
        runbook_ready=ready,
        required_item_count=required_count,
        completed_required_item_count=completed_count,
        items=[
            item_cls(
                runbook_id=item.item_id,
                status=status,
                required_for_activation=item.required_for_activation,
                notes=notes,
            )
            for item, status, notes in resolved
        ],
        **extra,
    )


def build_artifact_runbook_readiness() -> ArtifactRunbookReadinessResponse:
    return _build(
        "artifact",
        ArtifactRunbookReadinessItem,
        ArtifactRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_access_control_runbook_readiness() -> AccessControlRunbookReadinessResponse:
    return _build(
        "access_control",
        AccessControlRunbookReadinessItem,
        AccessControlRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_production_baseline_runbook_readiness() -> ProductionBaselineRunbookReadinessResponse:
    return _build(
        "production_baseline",
        ProductionBaselineRunbookReadinessItem,
        ProductionBaselineRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_deployment_split_runbook_readiness() -> DeploymentSplitRunbookReadinessResponse:
    return _build(
        "deployment_split",
        DeploymentSplitRunbookReadinessItem,
        DeploymentSplitRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_prompt_runbook_readiness() -> PromptRunbookReadinessResponse:
    return _build(
        "prompt",
        PromptRunbookReadinessItem,
        PromptRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_observability_runbook_readiness() -> ObservabilityRunbookReadinessResponse:
    return _build(
        "observability",
        ObservabilityRunbookReadinessItem,
        ObservabilityRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_resilience_runbook_readiness() -> ResilienceRunbookReadinessResponse:
    return _build(
        "resilience",
        ResilienceRunbookReadinessItem,
        ResilienceRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_first_use_case_runbook_readiness() -> FirstUseCaseRunbookReadinessResponse:
    return _build(
        "first_use_case",
        FirstUseCaseRunbookReadinessItem,
        FirstUseCaseRunbookReadinessResponse,
        version=settings.service_version,
        use_case_id=_FIRST_USE_CASE_ID,
        downstream_app=_FIRST_USE_CASE_CALLER_APP,
    )


def build_safety_runbook_readiness() -> SafetyRunbookReadinessResponse:
    return _build(
        "safety",
        SafetyRunbookReadinessItem,
        SafetyRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_retrieval_runbook_readiness() -> RetrievalRunbookReadinessResponse:
    return _build(
        "retrieval",
        RetrievalRunbookReadinessItem,
        RetrievalRunbookReadinessResponse,
        delivery_phase=settings.delivery_phase,
    )


def build_async_runbook_readiness() -> AsyncRunbookReadinessResponse:
    return _build(
        "async",
        AsyncRunbookReadinessItem,
        AsyncRunbookReadinessResponse,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
    )


def build_provider_runbook_readiness() -> ProviderRunbookReadinessResponse:
    return _build(
        "provider",
        ProviderRunbookReadinessItem,
        ProviderRunbookReadinessResponse,
        version=settings.service_version,
    )


def build_production_go_live_runbook_readiness() -> ProductionGoLiveRunbookReadinessResponse:
    return _build(
        "production_go_live",
        ProductionGoLiveRunbookReadinessItem,
        ProductionGoLiveRunbookReadinessResponse,
        version=settings.service_version,
        go_live_checklist=[
            "Confirm `/platform/production-go-live/runtime-status` reports platform production approval and the intended provider freeze or rollback posture.",
            "Confirm `/platform/production-go-live/activation-readiness` shows no remaining platform or provider blockers.",
            "Confirm `/platform/production-go-live/use-case-approval` distinguishes limited-rollout readiness from active-production approval for the named downstream path.",
            "Confirm `/platform/production-go-live/governance-status` and the embedded `production_go_live_governance` platform block match the detailed views before exposing real production traffic.",
        ],
    )
