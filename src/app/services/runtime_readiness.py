from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor


def _probe_sql_tables(expected_tables: Iterable[str]) -> tuple[RuntimeReadinessStatus, str]:
    if not settings.database_url:
        return (
            RuntimeReadinessStatus.CONFIGURATION_REQUIRED,
            "A database URL is required for the configured SQL-backed store mode.",
        )

    engine = create_engine(settings.database_url, future=True)
    try:
        with engine.connect():
            inspector = inspect(engine)
            missing_tables = [table for table in expected_tables if not inspector.has_table(table)]
    except SQLAlchemyError as exc:
        return (
            RuntimeReadinessStatus.UNAVAILABLE,
            f"Database connectivity check failed: {exc.__class__.__name__}.",
        )
    finally:
        engine.dispose()

    if missing_tables:
        missing_list = ", ".join(sorted(missing_tables))
        return (
            RuntimeReadinessStatus.MIGRATION_REQUIRED,
            f"Configured database is reachable but missing required tables: {missing_list}.",
        )

    return (
        RuntimeReadinessStatus.READY,
        "Configured database is reachable and required tables are present.",
    )


def get_audit_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.audit_store_mode,
        expected_tables=["audit_records"],
        memory_detail="In-memory audit store is active for local or foundation-phase execution.",
        unsupported_detail="Configured audit store mode is not supported by lotus-ai.",
    )


def get_retrieval_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.retrieval_store_mode,
        expected_tables=[
            "retrieval_sources",
            "retrieval_documents",
            "retrieval_chunks",
            "retrieval_index_jobs",
        ],
        memory_detail="In-memory retrieval metadata store is active for seeded platform catalog behavior.",
        unsupported_detail="Configured retrieval store mode is not supported by lotus-ai.",
    )


def get_access_control_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.access_control_store_mode,
        expected_tables=["caller_policies"],
        memory_detail="In-memory caller policy registry is active for foundation-phase access-control development.",
        unsupported_detail="Configured access-control store mode is not supported by lotus-ai.",
    )


def get_artifact_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.artifact_store_mode,
        expected_tables=["artifact_metadata"],
        memory_detail="In-memory artifact metadata store is active for local or foundation-phase development.",
        unsupported_detail="Configured artifact metadata store mode is not supported by lotus-ai.",
    )


def get_prompt_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.prompt_store_mode,
        expected_tables=[
            "prompt_definitions",
            "prompt_definition_versions",
            "prompt_rollout_state",
        ],
        memory_detail="In-memory prompt registry is active for local or foundation-phase prompt selection.",
        unsupported_detail="Configured prompt store mode is not supported by lotus-ai.",
    )


def get_provider_operations_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.provider_operations_store_mode,
        expected_tables=["provider_operations_state", "provider_operations_events"],
        memory_detail="In-memory provider-operations state is active for local or foundation-phase rollout work.",
        unsupported_detail="Configured provider-operations store mode is not supported by lotus-ai.",
    )


def get_async_runtime_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.async_runtime_store_mode,
        expected_tables=["async_jobs", "async_job_attempts", "async_control_events"],
        memory_detail="In-memory async runtime state is active for local or foundation-phase async execution.",
        unsupported_detail="Configured async runtime store mode is not supported by lotus-ai.",
    )


def get_evaluation_runtime_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.evaluation_runtime_store_mode,
        expected_tables=[
            "evaluation_runs",
            "evaluation_run_attempts",
            "evaluation_case_results",
        ],
        memory_detail="In-memory evaluation runtime state is active for local or foundation-phase runtime evidence.",
        unsupported_detail="Configured evaluation runtime store mode is not supported by lotus-ai.",
    )


def get_workflow_pack_run_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    return _build_store_runtime_status(
        configured_mode=settings.workflow_pack_run_store_mode,
        expected_tables=["workflow_pack_runs", "workflow_pack_run_events"],
        memory_detail="In-memory workflow-pack run ledger is active for foundation-phase runtime lineage work.",
        unsupported_detail="Configured workflow-pack run store mode is not supported by lotus-ai.",
    )


def _build_store_runtime_status(
    *,
    configured_mode: str,
    expected_tables: list[str],
    memory_detail: str,
    unsupported_detail: str,
) -> StoreRuntimeStatusDescriptor:
    if configured_mode == "memory":
        return StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=bool(settings.database_url),
            detail=memory_detail,
        )
    if configured_mode == "sqlalchemy":
        status_value, detail = _probe_sql_tables(expected_tables)
        return StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=status_value,
            database_configured=bool(settings.database_url),
            detail=detail,
        )
    return StoreRuntimeStatusDescriptor(
        mode=configured_mode,
        status=RuntimeReadinessStatus.UNAVAILABLE,
        database_configured=bool(settings.database_url),
        detail=unsupported_detail,
    )
