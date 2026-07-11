from __future__ import annotations

import json

from pydantic import TypeAdapter, ValidationError

from app.config import Settings
from app.contracts.workflow_run_model_risk import ApprovedWorkflowRunModel


_APPROVED_MODELS = TypeAdapter(list[ApprovedWorkflowRunModel])


class ConfiguredWorkflowRunModelRiskInventory:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def approved_models(self) -> list[ApprovedWorkflowRunModel]:
        try:
            models = _APPROVED_MODELS.validate_python(
                json.loads(self._settings.workflow_run_model_risk_inventory_json)
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(
                "workflow-run model-risk inventory must be valid governed JSON"
            ) from exc
        identities = [
            (
                model.provider_id,
                model.provider_mode,
                model.model_id,
                model.model_version,
                pack_id,
            )
            for model in models
            for pack_id in model.workflow_pack_ids
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("workflow-run model-risk inventory identities must be unique")
        return models
