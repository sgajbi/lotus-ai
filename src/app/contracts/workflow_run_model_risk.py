from pydantic import BaseModel, ConfigDict, Field


class ApprovedWorkflowRunModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=128)
    provider_mode: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=64)
    workflow_pack_ids: list[str] = Field(min_length=1)
    approval_ref: str = Field(min_length=1, max_length=256)
    approved_from_utc: str
    approved_until_utc: str | None = None
