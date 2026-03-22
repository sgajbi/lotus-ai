from app.config import settings
from app.contracts.tasks import CapabilityDescriptor, OutputLabel, TaskCategory
from app.services.task_execution_path import build_task_execution_path


def _capability(task_id: str, category: TaskCategory, output_label: OutputLabel) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        task_id=task_id,
        category=category,
        enabled=True,
        output_label=output_label,
        description="test capability",
    )


def test_task_execution_path_reports_retrieval_backed_search() -> None:
    descriptor = build_task_execution_path(
        _capability("knowledge_search.v1", TaskCategory.KNOWLEDGE_SEARCH, OutputLabel.RETRIEVAL_ANSWER)
    )

    assert descriptor.execution_path == "retrieval.catalog_search"
    assert descriptor.provider_mode == "catalog_only"
    assert descriptor.stubbed is False


def test_task_execution_path_reports_retrieval_backed_answer() -> None:
    descriptor = build_task_execution_path(
        _capability("knowledge_answer.v1", TaskCategory.KNOWLEDGE_ANSWER, OutputLabel.RETRIEVAL_ANSWER)
    )

    assert descriptor.execution_path == "retrieval.catalog_answer"
    assert descriptor.provider_mode == "catalog_answer"
    assert descriptor.stubbed is False


def test_task_execution_path_reports_provider_stub_for_supported_foundation_modes() -> None:
    descriptor = build_task_execution_path(
        _capability("explain.v1", TaskCategory.EXPLAIN, OutputLabel.EXPLANATION_ONLY)
    )

    assert descriptor.execution_path == "provider.stub_text"
    assert descriptor.provider_mode == "disabled"
    assert descriptor.stubbed is True
    assert "stub path" in descriptor.notes


def test_task_execution_path_reports_allowlisted_disabled_live_posture_honestly() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-4.1-mini"
    settings.live_text_provider_api_key = "secret"

    descriptor = build_task_execution_path(
        _capability("explain.v1", TaskCategory.EXPLAIN, OutputLabel.EXPLANATION_ONLY)
    )

    assert descriptor.execution_path == "provider.stub_text"
    assert descriptor.stubbed is True
    assert "allowlisted" in descriptor.notes


def test_task_execution_path_reports_blocked_provider_posture_for_unsupported_mode() -> None:
    settings.provider_mode = "openai"

    descriptor = build_task_execution_path(
        _capability("explain.v1", TaskCategory.EXPLAIN, OutputLabel.EXPLANATION_ONLY)
    )

    assert descriptor.execution_path == "provider.blocked_text"
    assert descriptor.provider_mode == "openai"
    assert descriptor.stubbed is True
    assert "will be rejected" in descriptor.notes
