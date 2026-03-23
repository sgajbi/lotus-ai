from pathlib import Path

from app.config import settings
from app.contracts.evals import EvaluationCaseOutcome
from app.evals.fixture_manifest import EvaluationFixtureRuntimeCase
from app.services.eval_runtime_execution import (
    _apply_case_configuration,
    _execute_fixture_case,
)
from app.services.provider_operations_store import reset_provider_operations_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def test_execute_fixture_case_reports_failure_for_provider_operations_state_mismatch() -> None:
    summary, outcome, evidence_refs = _execute_fixture_case(
        fixture_id="provider_operations_examples",
        fixture_task_id="provider_operations_examples",
        case=EvaluationFixtureRuntimeCase(
            case_id="provider_ops_mismatch_case",
            summary="Expect the wrong provider operations state.",
            input_payload={},
            expected_payload={"operations_state": "CIRCUIT_OPEN"},
        ),
    )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "did not match expected runtime evidence" in summary
    assert evidence_refs == ["service://platform/providers/operations-status"]


def test_execute_fixture_case_reports_pass_for_live_retrieval_search_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="retrieval_live_search_case",
        summary="Live retrieval should preserve citations.",
        input_payload={
            "task_id": "knowledge_search.v1",
            "query": "shared ai platform service",
            "retrieval_mode": "enabled",
            "index_sources": ["lotus-platform-rfcs"],
            "source_filters": ["lotus-platform-rfcs"],
        },
        expected_payload={
            "execution_stage": "LIVE_SEARCH",
            "provider_mode": "live_search",
            "catalog_only": False,
            "must_preserve_citations": True,
        },
    )
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="retrieval_citation_examples",
            fixture_task_id="knowledge_search.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "matched expected execution stage" in summary
    assert evidence_refs == [
        "service://ai/tasks/execute",
        "service://platform/retrieval/execution-status",
    ]


def test_execute_fixture_case_reports_unknown_runtime_semantics_for_unmapped_fixture() -> None:
    summary, outcome, evidence_refs = _execute_fixture_case(
        fixture_id="unknown_fixture_family",
        fixture_task_id="unknown_fixture_family",
        case=EvaluationFixtureRuntimeCase(
            case_id="unknown_fixture_case",
            summary="Unknown fixture family.",
            input_payload={},
            expected_payload={},
        ),
    )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "does not yet have runtime-backed execution semantics" in summary
    assert evidence_refs == ["fixture://unknown_fixture_family"]


def test_apply_case_configuration_supports_sqlalchemy_budget_and_degradation_paths(
    tmp_path: Path,
) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime-config.db'}"
    upgrade_database_to_head(settings.database_url)

    with _apply_case_configuration(
        {
            "provider_operations_store_mode": "sqlalchemy",
            "hard_budget_usd": 5.0,
            "tracked_spend_usd": 1.25,
            "degraded_failure_count_threshold": 1,
        }
    ):
        assert settings.provider_operations_store_mode == "sqlalchemy"
        assert settings.live_text_budget_enforced is True
        assert settings.live_text_degradation_enforced is True

    reset_provider_operations_store_cache()


def test_apply_case_configuration_supports_sqlalchemy_circuit_open_path(tmp_path: Path) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime-circuit.db'}"
    upgrade_database_to_head(settings.database_url)

    with _apply_case_configuration(
        {
            "provider_operations_store_mode": "sqlalchemy",
            "circuit_open_seconds": 30,
        }
    ):
        assert settings.provider_operations_store_mode == "sqlalchemy"
        assert settings.live_text_circuit_open_seconds == 30

    reset_provider_operations_store_cache()
