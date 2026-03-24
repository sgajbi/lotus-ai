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
    if settings.audit_store_mode == "memory":
        return StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=bool(settings.database_url),
            detail="In-memory audit store is active for local or foundation-phase execution.",
        )
    if settings.audit_store_mode == "sqlalchemy":
        status_value, detail = _probe_sql_tables(["audit_records"])
        return StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=status_value,
            database_configured=bool(settings.database_url),
            detail=detail,
        )
    return StoreRuntimeStatusDescriptor(
        mode=settings.audit_store_mode,
        status=RuntimeReadinessStatus.UNAVAILABLE,
        database_configured=bool(settings.database_url),
        detail="Configured audit store mode is not supported by lotus-ai.",
    )


def get_retrieval_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    if settings.retrieval_store_mode == "memory":
        return StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=bool(settings.database_url),
            detail="In-memory retrieval metadata store is active for seeded platform catalog behavior.",
        )
    if settings.retrieval_store_mode == "sqlalchemy":
        status_value, detail = _probe_sql_tables(
            [
                "retrieval_sources",
                "retrieval_documents",
                "retrieval_chunks",
                "retrieval_index_jobs",
            ]
        )
        return StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=status_value,
            database_configured=bool(settings.database_url),
            detail=detail,
        )
    return StoreRuntimeStatusDescriptor(
        mode=settings.retrieval_store_mode,
        status=RuntimeReadinessStatus.UNAVAILABLE,
        database_configured=bool(settings.database_url),
        detail="Configured retrieval store mode is not supported by lotus-ai.",
    )


def get_access_control_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    if settings.access_control_store_mode == "memory":
        return StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=bool(settings.database_url),
            detail="In-memory caller policy registry is active for foundation-phase access-control development.",
        )
    if settings.access_control_store_mode == "sqlalchemy":
        status_value, detail = _probe_sql_tables(["caller_policies"])
        return StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=status_value,
            database_configured=bool(settings.database_url),
            detail=detail,
        )
    return StoreRuntimeStatusDescriptor(
        mode=settings.access_control_store_mode,
        status=RuntimeReadinessStatus.UNAVAILABLE,
        database_configured=bool(settings.database_url),
        detail="Configured access-control store mode is not supported by lotus-ai.",
    )


def get_artifact_store_runtime_status() -> StoreRuntimeStatusDescriptor:
    if settings.artifact_store_mode == "memory":
        return StoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            database_configured=bool(settings.database_url),
            detail="In-memory artifact metadata store is active for local or foundation-phase development.",
        )
    if settings.artifact_store_mode == "sqlalchemy":
        status_value, detail = _probe_sql_tables(["artifact_metadata"])
        return StoreRuntimeStatusDescriptor(
            mode="sqlalchemy",
            status=status_value,
            database_configured=bool(settings.database_url),
            detail=detail,
        )
    return StoreRuntimeStatusDescriptor(
        mode=settings.artifact_store_mode,
        status=RuntimeReadinessStatus.UNAVAILABLE,
        database_configured=bool(settings.database_url),
        detail="Configured artifact metadata store mode is not supported by lotus-ai.",
    )
