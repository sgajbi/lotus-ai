from app.config import settings
from app.contracts.safety import SafetyExecutionDisposition

from app.services.safety_status import build_safety_runtime_status


def test_safety_runtime_status_reports_enforced_and_documented_controls() -> None:
    status = build_safety_runtime_status()

    assert status.service == "lotus-ai"
    assert status.safety_mode == "documented_only"
    # Issue #150 slice 2: the redaction engine enforces independently of
    # the safety mode.
    assert status.runtime_redaction_active is True
    assert status.runtime_redaction_disposition == "ENFORCED_PASSTHROUGH"
    assert status.enforced_control_ids == [
        "response_labeling",
        "correlation_and_audit",
        "runtime_redaction_engine",
    ]
    assert "runtime_redaction_engine" in status.enforced_control_ids
    assert status.supported_execution_dispositions == ["DOCUMENTED_ONLY"]
    assert status.task_policy_count >= 7


def test_safety_runtime_status_reports_active_redaction_when_runtime_enforced() -> None:
    settings.safety_mode = "runtime_enforced"

    status = build_safety_runtime_status()

    assert status.safety_mode == "runtime_enforced"
    # Truthful posture (issue #150): no redaction engine exists, so the
    # redaction fields stay documented-only even under runtime_enforced.
    assert status.runtime_redaction_active is True
    assert status.runtime_redaction_disposition == SafetyExecutionDisposition.ENFORCED_PASSTHROUGH
    assert "structured_output_key_minimization" in status.enforced_control_ids
    assert "runtime_redaction_engine" in status.enforced_control_ids
    assert "ENFORCED_REDACTED" in status.supported_execution_dispositions

    settings.safety_mode = "documented_only"
