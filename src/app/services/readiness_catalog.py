"""Readiness as data (issue #154, S1).

Ten near-identical runbook-readiness modules carried their operational
posture as hard-coded ``status="READY"`` literals - forty-odd endpoint
values that could not change when operational reality changed. This module
replaces them with one catalog
(``contracts/readiness/runbook_readiness_catalog.json``) and one builder:

- every item declares an ``execution_state`` in ``{ENFORCED, PARTIAL,
  DOCUMENTED_ONLY, OUT_OF_SCOPE}``; a state not computed from runtime
  evidence is ``DOCUMENTED_ONLY``, never ``READY`` - the API now says what
  is actually true;
- ``runbook_ready`` is derived (every required item ``ENFORCED``), never
  asserted;
- the per-domain response contracts are unchanged in shape, so consumers
  keep parsing what they parsed before - only the honesty of the values
  changed.

The provider runbook readiness stays in its own module for now: its notes
interpolate live rollout posture and the go-live surface consumes it; it
migrates with the mixed/computed group in the next slice.
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

EXECUTION_STATES = frozenset({"ENFORCED", "PARTIAL", "DOCUMENTED_ONLY", "OUT_OF_SCOPE"})

_FIRST_USE_CASE_ID = "lotus_performance.analytics_commentary.v1"
_FIRST_USE_CASE_CALLER_APP = "lotus-performance"


class CatalogRunbookItem(BaseModel):
    item_id: str
    execution_state: str
    required_for_activation: bool
    notes: str


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
        catalog[domain] = items
    return catalog


def reset_readiness_catalog_cache() -> None:
    _load_catalog.cache_clear()


def catalog_runbook_items(domain: str) -> list[CatalogRunbookItem]:
    catalog = _load_catalog()
    if domain not in catalog:
        raise ValueError(f"runbook readiness catalog has no domain '{domain}'")
    return list(catalog[domain])


def _summarize(items: list[CatalogRunbookItem]) -> tuple[int, int, bool]:
    required = [item for item in items if item.required_for_activation]
    enforced = [item for item in required if item.execution_state == "ENFORCED"]
    return len(required), len(enforced), bool(required) and len(enforced) == len(required)


_TResponse = TypeVar("_TResponse", bound=BaseModel)


def _build(
    domain: str, item_cls: type[BaseModel], response_cls: type[_TResponse], **extra: object
) -> _TResponse:
    items = catalog_runbook_items(domain)
    required_count, completed_count, ready = _summarize(items)
    return response_cls(
        service=settings.service_name,
        runbook_ready=ready,
        required_item_count=required_count,
        completed_required_item_count=completed_count,
        items=[
            item_cls(
                runbook_id=item.item_id,
                status=item.execution_state,
                required_for_activation=item.required_for_activation,
                notes=item.notes,
            )
            for item in items
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
