from app.config import settings
from app.services.task_runtime_status import build_task_runtime_status


def test_task_runtime_status_reports_retrieval_and_stubbed_task_mix() -> None:
    status = build_task_runtime_status()

    assert status.enabled_task_count == 7
    assert status.stubbed_task_count == 5
    assert status.retrieval_backed_task_count == 2
    assert any(task.execution_path == "retrieval.catalog_search" for task in status.tasks)
    assert any(task.execution_path == "provider.stub_text" for task in status.tasks)


def test_task_runtime_status_reports_blocked_provider_path_when_mode_is_unsupported() -> None:
    settings.provider_mode = "openai"

    status = build_task_runtime_status()

    explain_task = next(task for task in status.tasks if task.task_id == "explain.v1")
    assert explain_task.execution_path == "provider.blocked_text"
    assert explain_task.provider_mode == "openai"
