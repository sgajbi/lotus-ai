from __future__ import annotations

from app.config import settings
from app.contracts.safety import (
    SafetyControlStatus,
    SafetyExecutionDisposition,
    SafetyRuntimeStatusResponse,
)
from app.services.safety_policy import build_safety_policy


def build_safety_runtime_status() -> SafetyRuntimeStatusResponse:
    policy = build_safety_policy()
    enforced_control_ids = [
        control.control_id
        for control in policy.controls
        if control.status == SafetyControlStatus.ENFORCED
    ]
    documented_only_control_ids = [
        control.control_id
        for control in policy.controls
        if control.status == SafetyControlStatus.DOCUMENTED
    ]
    return SafetyRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        safety_mode=settings.safety_mode,
        runtime_redaction_active=False,
        runtime_redaction_disposition=SafetyExecutionDisposition.DOCUMENTED_ONLY,
        enforced_control_ids=enforced_control_ids,
        documented_only_control_ids=documented_only_control_ids,
        supported_execution_dispositions=[SafetyExecutionDisposition.DOCUMENTED_ONLY],
        task_policy_count=len(policy.task_policies),
    )
