from fastapi import HTTPException

from app.contracts.tasks import OutputLabel
from app.services.task_capability_validator import validate_task_capability
from tests.unit.test_task_executor import _request


def test_validate_task_capability_returns_enabled_capability() -> None:
    capability = validate_task_capability(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert capability.task_id == "explain.v1"
    assert capability.enabled is True
    assert capability.output_label == OutputLabel.EXPLANATION_ONLY


def test_validate_task_capability_rejects_unknown_task() -> None:
    try:
        validate_task_capability(_request("missing.v1"))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "Unknown lotus-ai task_id" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown task")


def test_validate_task_capability_rejects_output_label_mismatch() -> None:
    try:
        validate_task_capability(_request("explain.v1", expected_output_label=OutputLabel.DRAFT))
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Expected output label does not match task configuration" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for output label mismatch")
