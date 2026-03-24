from pathlib import Path

from app.services.observability_domain_summaries import (
    build_async_observability_bundle,
    build_evaluation_observability_bundle,
    build_prompt_observability_bundle,
    build_provider_observability_bundle,
    build_retrieval_observability_bundle,
    build_safety_observability_bundle,
)
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_provider_observability_bundle_surfaces_rollout_blocked_incident() -> None:
    bundle = build_provider_observability_bundle()

    assert bundle.summary.domain_id == "provider"
    assert bundle.summary.telemetry.incident_evidence_supported is True
    assert bundle.summary.telemetry.incident_signal_count >= 1
    assert (
        bundle.summary.incident_evidence_items[0].evidence_id
        == "provider_operations_incident_state"
    )


def test_retrieval_observability_bundle_marks_sql_store_incident_evidence_durable(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'observability-retrieval.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        retrieval_mode="enabled",
        retrieval_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        bundle = build_retrieval_observability_bundle()

    assert bundle.summary.domain_id == "retrieval"
    assert bundle.summary.incident_evidence_items[0].durable is True


def test_async_observability_bundle_surfaces_degraded_fallback() -> None:
    with override_runtime_settings(
        async_cutover_state="degraded_fallback",
        async_queue_backend_mode="redis",
        async_queue_redis_url="redis://localhost:6379/0",
    ):
        bundle = build_async_observability_bundle()

    assert bundle.summary.domain_id == "async"
    assert bundle.summary.telemetry.posture == "DEGRADED"
    assert bundle.summary.incident_evidence_items[0].posture == "DEGRADED"


def test_evaluation_observability_bundle_surfaces_runtime_approval_evidence() -> None:
    bundle = build_evaluation_observability_bundle()

    assert bundle.summary.domain_id == "evaluation"
    assert bundle.summary.telemetry.incident_evidence_supported is True
    assert bundle.summary.incident_evidence_items[0].evidence_id == "evaluation_approval_gate_state"


def test_prompt_observability_bundle_surfaces_blocked_activation_path() -> None:
    bundle = build_prompt_observability_bundle()

    assert bundle.summary.domain_id == "prompt"
    assert bundle.summary.telemetry.incident_evidence_supported is True
    assert bundle.summary.incident_evidence_items[0].evidence_id == "prompt_rollout_approval_state"


def test_safety_observability_bundle_surfaces_runtime_enforcement_state() -> None:
    bundle = build_safety_observability_bundle()

    assert bundle.summary.domain_id == "safety"
    assert bundle.summary.telemetry.incident_evidence_supported is True
    assert (
        bundle.summary.incident_evidence_items[0].evidence_id == "safety_runtime_enforcement_state"
    )
