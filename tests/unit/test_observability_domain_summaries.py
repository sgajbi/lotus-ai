from pathlib import Path

from app.contracts.artifacts import ArtifactLifecycleStatus
from app.services.artifact_store import (
    get_artifact_object_store,
    get_artifact_repository,
    reset_artifact_store_cache,
)
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
    assert len(bundle.summary.incident_evidence_items[0].artifact_refs) == 1
    assert bundle.summary.incident_evidence_items[0].artifact_refs[0].domain == "observability"


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
    assert len(bundle.summary.incident_evidence_items) == 2
    assert (
        bundle.summary.incident_evidence_items[1].evidence_id
        == "retrieval_corpus_change_runtime_state"
    )


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


def test_observability_bundle_reuses_existing_artifact_when_payload_is_unchanged() -> None:
    first = build_provider_observability_bundle()
    second = build_provider_observability_bundle()

    first_artifact = first.summary.incident_evidence_items[0].artifact_refs[0]
    second_artifact = second.summary.incident_evidence_items[0].artifact_refs[0]

    assert first_artifact.artifact_id == second_artifact.artifact_id
    assert len(get_artifact_repository().list_artifacts()) == 1


def test_observability_bundle_supersedes_prior_artifact_when_posture_changes(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'observability-lineage.db'}"
    object_root = str(tmp_path / "observability-lineage-objects")
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        artifact_store_mode="sqlalchemy",
        artifact_object_store_mode="filesystem",
        artifact_object_store_root=object_root,
        database_url=database_url,
    ):
        healthy = build_async_observability_bundle()
        with override_runtime_settings(
            artifact_store_mode="sqlalchemy",
            artifact_object_store_mode="filesystem",
            artifact_object_store_root=object_root,
            database_url=database_url,
            async_cutover_state="degraded_fallback",
            async_queue_backend_mode="redis",
            async_queue_redis_url="redis://localhost:6379/0",
        ):
            degraded = build_async_observability_bundle()
        records = get_artifact_repository().list_artifacts()

    healthy_artifact = healthy.summary.incident_evidence_items[0].artifact_refs[0]
    degraded_artifact = degraded.summary.incident_evidence_items[0].artifact_refs[0]
    superseded = next(
        record for record in records if record.artifact_id == healthy_artifact.artifact_id
    )

    assert degraded_artifact.artifact_id != healthy_artifact.artifact_id
    assert len(records) == 2
    assert superseded.lifecycle_status == ArtifactLifecycleStatus.SUPERSEDED
    assert superseded.superseded_by_artifact_id == degraded_artifact.artifact_id


def test_observability_bundle_persists_sql_backed_incident_artifact(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'observability-artifacts.db'}"
    object_root = str(tmp_path / "artifact-payloads")
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        artifact_store_mode="sqlalchemy",
        artifact_object_store_mode="filesystem",
        artifact_object_store_root=object_root,
        database_url=database_url,
    ):
        bundle = build_evaluation_observability_bundle()
        artifact = bundle.summary.incident_evidence_items[0].artifact_refs[0]
        object_key = artifact.storage_reference.split("://", 1)[1]
        reset_artifact_store_cache()
        persisted = get_artifact_repository().get_artifact(artifact_id=artifact.artifact_id)
        stored_object = get_artifact_object_store().get_object(object_key=object_key)

    assert persisted is not None
    assert stored_object is not None
    assert persisted.domain == "observability"
