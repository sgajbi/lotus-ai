from app.contracts.tasks import OutputLabel, TaskCategory
from app.services.capability_catalog import build_capability_catalog


def test_build_capability_catalog_returns_expected_phase_and_tasks() -> None:
    catalog = build_capability_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.phase == "foundation"
    assert len(catalog.tasks) == 7
    assert catalog.tasks[0].task_id == "explain.v1"
    assert catalog.tasks[0].category == TaskCategory.EXPLAIN
    assert catalog.tasks[0].output_label == OutputLabel.EXPLANATION_ONLY


def test_retrieval_tasks_enable_search_but_not_answer_in_foundation_phase() -> None:
    catalog = build_capability_catalog()

    retrieval_tasks = {
        task.task_id: task.enabled
        for task in catalog.tasks
        if task.category in {TaskCategory.KNOWLEDGE_SEARCH, TaskCategory.KNOWLEDGE_ANSWER}
    }

    assert retrieval_tasks == {
        "knowledge_search.v1": True,
        "knowledge_answer.v1": False,
    }
