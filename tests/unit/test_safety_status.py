from app.config import settings
from app.services.safety_status import build_safety_runtime_status


def test_safety_runtime_status_reports_enforced_and_documented_controls() -> None:
    status = build_safety_runtime_status()

    assert status.service == "lotus-ai"
    assert status.safety_mode == "documented_only"
    assert status.runtime_redaction_active is False
    assert status.runtime_redaction_disposition == "DOCUMENTED_ONLY"
    assert status.enforced_control_ids == ["response_labeling", "correlation_and_audit"]
    assert "runtime_redaction_engine" in status.documented_only_control_ids
    assert status.supported_execution_dispositions == ["DOCUMENTED_ONLY"]
    assert status.task_policy_count >= 7


def test_safety_runtime_status_reports_active_redaction_when_runtime_enforced() -> None:
    settings.safety_mode = "runtime_enforced"

    status = build_safety_runtime_status()

    assert status.safety_mode == "runtime_enforced"
    assert status.runtime_redaction_active is True
    assert status.runtime_redaction_disposition == "ENFORCED_PASSTHROUGH"
    assert "runtime_redaction_engine" in status.enforced_control_ids
    assert "ENFORCED_REDACTED" in status.supported_execution_dispositions

    settings.safety_mode = "documented_only"
