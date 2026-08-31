"""Readiness as data (issue #154, S1).

Ten copy-paste runbook-readiness modules are one catalog and one builder;
statuses not computed from runtime evidence are DOCUMENTED_ONLY, never
READY; readiness is derived from execution states, never asserted; a
catalog change is visible on the endpoint without a code change.
"""

import json
from collections.abc import Generator
from pathlib import Path

import pytest

from app.services import readiness_catalog
from app.services.readiness_catalog import (
    build_access_control_runbook_readiness,
    build_artifact_runbook_readiness,
    build_first_use_case_runbook_readiness,
    build_observability_runbook_readiness,
    build_retrieval_runbook_readiness,
    build_safety_runbook_readiness,
    catalog_runbook_items,
    reset_readiness_catalog_cache,
)

DOMAINS = [
    "artifact",
    "access_control",
    "production_baseline",
    "deployment_split",
    "prompt",
    "observability",
    "resilience",
    "first_use_case",
    "safety",
    "retrieval",
]


@pytest.fixture(autouse=True)
def _fresh_catalog_cache() -> Generator[None, None, None]:
    reset_readiness_catalog_cache()
    yield
    reset_readiness_catalog_cache()


def test_every_catalog_domain_resolves_with_honest_states() -> None:
    for domain in DOMAINS:
        items = catalog_runbook_items(domain)
        assert items, f"domain {domain} has no items"
        for item in items:
            assert item.execution_state in readiness_catalog.EXECUTION_STATES
            # Nothing in the catalog claims READY: readiness is derived,
            # and no current item is backed by runtime enforcement.
            assert item.execution_state != "READY"


def test_documented_only_items_never_produce_a_ready_surface() -> None:
    for build in (
        build_artifact_runbook_readiness,
        build_access_control_runbook_readiness,
        build_safety_runbook_readiness,
    ):
        response = build()
        assert response.runbook_ready is False
        assert response.completed_required_item_count == 0
        assert all(item.status in readiness_catalog.EXECUTION_STATES for item in response.items)


def test_out_of_scope_and_optional_items_do_not_count_as_required() -> None:
    response = build_observability_runbook_readiness()
    optional = [item for item in response.items if not item.required_for_activation]
    assert any(item.status == "OUT_OF_SCOPE" for item in optional)
    assert response.required_item_count == len(
        [item for item in response.items if item.required_for_activation]
    )


def test_domain_variant_fields_are_preserved() -> None:
    first_use_case = build_first_use_case_runbook_readiness()
    assert first_use_case.use_case_id == "lotus_performance.analytics_commentary.v1"
    assert first_use_case.downstream_app == "lotus-performance"
    retrieval = build_retrieval_runbook_readiness()
    assert retrieval.delivery_phase


def test_a_catalog_change_is_visible_without_a_code_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issue's evaluation condition: flip one item to ENFORCED in the
    catalog and the endpoint surface changes - readiness is data."""

    real = json.loads(Path(readiness_catalog._CATALOG_PATH).read_text(encoding="utf-8"))
    for item in real["safety"]["items"]:
        item["execution_state"] = "ENFORCED"
    override = tmp_path / "runbook_readiness_catalog.json"
    override.write_text(json.dumps(real), encoding="utf-8")
    monkeypatch.setattr(readiness_catalog, "_CATALOG_PATH", override)
    reset_readiness_catalog_cache()

    response = build_safety_runbook_readiness()
    assert response.runbook_ready is True
    assert response.completed_required_item_count == response.required_item_count
    assert all(item.status == "ENFORCED" for item in response.items)


def test_unknown_domain_and_unknown_state_fail_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="no domain 'nonexistent'"):
        catalog_runbook_items("nonexistent")

    corrupt = tmp_path / "runbook_readiness_catalog.json"
    corrupt.write_text(
        json.dumps(
            {
                "safety": {
                    "family": "runbook",
                    "items": [
                        {
                            "item_id": "x",
                            "execution_state": "READY",
                            "required_for_activation": True,
                            "notes": "a literal READY must be refused",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(readiness_catalog, "_CATALOG_PATH", corrupt)
    reset_readiness_catalog_cache()
    with pytest.raises(ValueError, match="unknown execution_state 'READY'"):
        catalog_runbook_items("safety")
