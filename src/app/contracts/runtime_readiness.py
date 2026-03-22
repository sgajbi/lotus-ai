from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RuntimeReadinessStatus(str, Enum):
    READY = "READY"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


class StoreRuntimeStatusDescriptor(BaseModel):
    mode: str = Field(description="Configured store mode for the runtime component.")
    status: RuntimeReadinessStatus = Field(description="Current readiness status for the store.")
    database_configured: bool = Field(
        description="Whether a database URL is configured for this store."
    )
    detail: str = Field(description="Human-readable explanation of the current readiness status.")
