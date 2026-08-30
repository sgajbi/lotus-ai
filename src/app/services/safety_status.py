from __future__ import annotations

from app.config import settings
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.services.redaction_engine import REDACTION_MODE_ENFORCE
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
        safety_mode=resolve_runtime_mode_config().safety_mode,
        # The deterministic redaction engine (issue #150 slice 2) screens
        # generated content independently of safety mode; it is active when
        # the redaction mode is enforce, and observing otherwise.
        runtime_redaction_active=(
            resolve_runtime_mode_config().redaction_mode == REDACTION_MODE_ENFORCE
        ),
        runtime_redaction_disposition=(
            SafetyExecutionDisposition.ENFORCED_PASSTHROUGH
            if resolve_runtime_mode_config().redaction_mode == REDACTION_MODE_ENFORCE
            else SafetyExecutionDisposition.DOCUMENTED_ONLY
        ),
        enforced_control_ids=enforced_control_ids,
        documented_only_control_ids=documented_only_control_ids,
        supported_execution_dispositions=(
            [
                SafetyExecutionDisposition.ENFORCED_PASSTHROUGH,
                SafetyExecutionDisposition.ENFORCED_REDACTED,
                SafetyExecutionDisposition.BLOCKED,
                SafetyExecutionDisposition.DEGRADED,
            ]
            if resolve_runtime_mode_config().safety_mode == "runtime_enforced"
            else [SafetyExecutionDisposition.DOCUMENTED_ONLY]
        ),
        task_policy_count=len(policy.task_policies),
    )
