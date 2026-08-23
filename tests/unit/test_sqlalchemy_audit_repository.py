from pathlib import Path

from pytest import MonkeyPatch

from sqlalchemy import text

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.audit import AuditRecordResponse
from app.contracts.audit_access import (
    AuditAccessEvent,
    AuditAccessOperation,
    AuditAccessOutcome,
    AuditReadScope,
)
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.prompts import PromptRolloutRole, PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderAdapterKind
from app.contracts.safety import RedactionPosture, SafetyExecutionDisposition
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
from app.repositories.sqlalchemy_audit_repository import (
    _default_adapter_kind,
    _default_provider_id,
)
from app.services.safety_runtime import build_safety_execution_outcome_from_record
from tests.support.migration_runner import upgrade_database_to_head


def _prompt_selection(prompt_version: str) -> PromptSelectionTraceDescriptor:
    return PromptSelectionTraceDescriptor(
        task_id="explain.v1",
        prompt_version=prompt_version,
        rollout_role=PromptRolloutRole.ACTIVE,
        selection_reason="Runtime selection resolved through durable prompt rollout state.",
        active_prompt_version=prompt_version,
        candidate_prompt_version=None,
        previous_active_prompt_version=None,
        latest_control_event=None,
    )


def _authorization(
    *,
    task_id: str = "explain.v1",
    tenant_id: str | None = "tenant-sg-001",
) -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        task_id=task_id,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=tenant_id,
        summary="Caller is authorized for bounded task execution.",
    )


def test_sqlalchemy_audit_repository_save_and_get(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    record = AuditRecordResponse(
        request_id="air_sql_1",
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-sql-1",
        requested_by="ops.user@lotus",
        tenant_id="tenant-sg-001",
        prompt_version="foundation.explain.v1",
        prompt_selection=_prompt_selection("foundation.explain.v1"),
        provider_mode="disabled",
        provider_id="text.stub",
        adapter_kind=ProviderAdapterKind.STUB,
        model_id=None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.EXPLANATION_ONLY,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling", "correlation_and_audit"],
        ),
        authorization=_authorization(),
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Explain rebalance outcome",
        context_keys=["status"],
        source_refs=["lotus-manage:run:reb_sql_1"],
        result_preview="Stub execution completed.",
        structured_output={"phase": "foundation"},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )

    repository.save(record)

    scope = AuditReadScope.restricted(frozenset({"tenant-sg-001"}))
    loaded = repository.get("air_sql_1", scope=scope)
    assert loaded == record
    assert loaded.prompt_selection.prompt_version == "foundation.explain.v1"
    assert repository.get("air_missing", scope=scope) is None


def test_sqlalchemy_audit_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-audit.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyAuditRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_audit_repository_list_filters_and_orders_latest_first(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-list.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    old_record = AuditRecordResponse(
        request_id="air_sql_old",
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-sql-old",
        requested_by="ops.user@lotus",
        tenant_id="tenant-sg-001",
        prompt_version="foundation.explain.v1",
        prompt_selection=_prompt_selection("foundation.explain.v1"),
        provider_mode="disabled",
        provider_id="text.stub",
        adapter_kind=ProviderAdapterKind.STUB,
        model_id=None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.EXPLANATION_ONLY,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling", "correlation_and_audit"],
        ),
        authorization=_authorization(),
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Old",
        context_keys=["status"],
        source_refs=[],
        result_preview="Old",
        structured_output={},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )
    new_record = old_record.model_copy(
        update={
            "request_id": "air_sql_new",
            "task_id": "summarize.v1",
            "category": TaskCategory.SUMMARIZE,
            "output_label": OutputLabel.DRAFT,
            "caller_app": "lotus-advise",
            "requested_by": "advisor.user@lotus",
            "tenant_id": "tenant-us-002",
            "generated_at": "2026-03-22T01:00:00Z",
        }
    )

    repository.save(old_record)
    repository.save(new_record)

    all_scope = AuditReadScope.all_tenants()
    us_scope = AuditReadScope.restricted(frozenset({"tenant-us-002"}))
    all_records = repository.list(scope=all_scope)
    advise_records = repository.list(scope=all_scope, caller_app="lotus-advise", limit=10)
    summarize_records = repository.list(scope=all_scope, category="summarize", limit=10)
    draft_records = repository.list(scope=all_scope, output_label="DRAFT", limit=10)
    tenant_records = repository.list(scope=us_scope, limit=10)
    requester_records = repository.list(
        scope=all_scope,
        requested_by="advisor.user@lotus",
        limit=10,
    )

    assert [record.request_id for record in all_records] == ["air_sql_new", "air_sql_old"]
    assert [record.request_id for record in advise_records] == ["air_sql_new"]
    assert [record.request_id for record in summarize_records] == ["air_sql_new"]
    assert [record.request_id for record in draft_records] == ["air_sql_new"]
    assert [record.request_id for record in tenant_records] == ["air_sql_new"]
    assert [record.request_id for record in requester_records] == ["air_sql_new"]
    assert (
        repository.get(
            "air_sql_new",
            scope=AuditReadScope.restricted(frozenset({"tenant-sg-001"})),
        )
        is None
    )


def test_sqlalchemy_audit_repository_round_trips_access_event(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-access.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)
    event = AuditAccessEvent(
        event_id="audit_access_sql_001",
        caller_app="lotus-platform",
        caller_trust_source="trusted_http_header",
        scope_mode="ALL_TENANTS",
        operation=AuditAccessOperation.GET_RECORD,
        outcome=AuditAccessOutcome.NOT_FOUND,
        returned_record_count=0,
        recorded_at="2026-08-23T00:00:00Z",
    )

    repository.save_access_event(event)

    assert list(repository.list_access_events()) == [event]


def test_sqlalchemy_audit_repository_round_trips_exact_blocked_safety_outcome(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-blocked.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    blocked_outcome = build_safety_execution_outcome_from_record(
        safety_mode="runtime_enforced",
        output_label=OutputLabel.EXPLANATION_ONLY,
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_controls=[
            "response_labeling",
            "correlation_and_audit",
            "runtime_redaction_engine",
        ],
    ).model_copy(
        update={
            "disposition": SafetyExecutionDisposition.BLOCKED,
            "runtime_redaction_active": True,
            "decision_summary": "Blocked because unsupported raw context echo fields were returned.",
        }
    )

    record = AuditRecordResponse(
        request_id="air_sql_blocked",
        execution_status=TaskExecutionStatus.REJECTED,
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-sql-blocked",
        requested_by="ops.user@lotus",
        tenant_id="tenant-sg-001",
        prompt_version="foundation.explain.v1",
        prompt_selection=_prompt_selection("foundation.explain.v1"),
        provider_mode="stub",
        provider_id="text.stub",
        adapter_kind=ProviderAdapterKind.STUB,
        model_id=None,
        safety_mode="runtime_enforced",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=[
            "response_labeling",
            "correlation_and_audit",
            "runtime_redaction_engine",
        ],
        safety_outcome=blocked_outcome,
        authorization=_authorization(),
        generated_at="2026-03-23T00:00:00Z",
        stubbed=True,
        context_summary="Explain rebalance outcome",
        context_keys=["status"],
        source_refs=["lotus-manage:run:reb_sql_blocked"],
        result_preview="Task output blocked by deterministic runtime safety enforcement.",
        structured_output={"safety_blocked": True},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="safety_outcome",
                    summary="Blocked by runtime safety.",
                    attributes={"disposition": "BLOCKED"},
                )
            ]
        ),
    )

    repository.save(record)

    loaded = repository.get(
        "air_sql_blocked",
        scope=AuditReadScope.restricted(frozenset({"tenant-sg-001"})),
    )
    assert loaded == record
    assert loaded.prompt_selection.prompt_version == "foundation.explain.v1"


def test_sqlalchemy_audit_repository_falls_back_for_legacy_records_without_safety_payload(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-legacy.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    with repository._engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO audit_records (
                    request_id,
                    execution_status,
                    task_id,
                    category,
                    output_label,
                    caller_app,
                    correlation_id,
                    requested_by,
                    tenant_id,
                    prompt_version,
                    provider_mode,
                    safety_mode,
                    redaction_posture,
                    enforced_safety_controls,
                    generated_at,
                    stubbed,
                    context_summary,
                    context_keys,
                    source_refs,
                    result_preview,
                    structured_output,
                    evidence,
                    safety_outcome_payload,
                    authorization_payload
                ) VALUES (
                    :request_id,
                    :execution_status,
                    :task_id,
                    :category,
                    :output_label,
                    :caller_app,
                    :correlation_id,
                    :requested_by,
                    :tenant_id,
                    :prompt_version,
                    :provider_mode,
                    :safety_mode,
                    :redaction_posture,
                    :enforced_safety_controls,
                    :generated_at,
                    :stubbed,
                    :context_summary,
                    :context_keys,
                    :source_refs,
                    :result_preview,
                    :structured_output,
                    :evidence,
                    NULL,
                    NULL
                )
                """
            ),
            {
                "request_id": "air_sql_legacy",
                "execution_status": "COMPLETED",
                "task_id": "explain.v1",
                "category": "explain",
                "output_label": "EXPLANATION_ONLY",
                "caller_app": "lotus-manage",
                "correlation_id": "corr-legacy",
                "requested_by": "ops.user@lotus",
                "tenant_id": "tenant-sg-001",
                "prompt_version": "foundation.explain.v1",
                "provider_mode": "disabled",
                "safety_mode": "documented_only",
                "redaction_posture": "MINIMIZATION_REQUIRED",
                "enforced_safety_controls": '["response_labeling","correlation_and_audit"]',
                "generated_at": "2026-03-23T01:00:00Z",
                "stubbed": True,
                "context_summary": "Explain rebalance outcome",
                "context_keys": '["status"]',
                "source_refs": '["lotus-manage:run:reb_legacy"]',
                "result_preview": "Stub execution completed.",
                "structured_output": "{}",
                "evidence": '{"descriptors":[]}',
            },
        )

    loaded = repository.get("air_sql_legacy", scope=AuditReadScope.all_tenants())
    assert loaded is not None
    assert loaded.execution_status == TaskExecutionStatus.COMPLETED
    assert loaded.safety_outcome.disposition == SafetyExecutionDisposition.DOCUMENTED_ONLY
    assert loaded.prompt_selection.prompt_version == "foundation.explain.v1"
    assert loaded.prompt_selection.latest_control_event is None
    assert loaded.authorization.outcome == AuthorizationOutcome.ALLOWED


def test_sqlalchemy_audit_repository_round_trips_authorization_payload(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-audit-authorization.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAuditRepository(database_url)

    authorization = AuthorizationDecision(
        caller_app="lotus-workbench",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id="knowledge_search.v1",
        requested_source_ids=["lotus-platform-rfcs"],
        effective_source_ids=["lotus-platform-rfcs"],
        tenant_id=None,
        summary="Caller is authorized for governed knowledge search execution.",
    )
    record = AuditRecordResponse(
        request_id="air_sql_authorized",
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id="knowledge_search.v1",
        category=TaskCategory.KNOWLEDGE_SEARCH,
        output_label=OutputLabel.RETRIEVAL_ANSWER,
        caller_app="lotus-workbench",
        correlation_id="corr-sql-authorized",
        requested_by=None,
        tenant_id=None,
        prompt_version="foundation.knowledge_search.v1",
        prompt_selection=_prompt_selection("foundation.knowledge_search.v1"),
        provider_mode="catalog_only",
        provider_id="retrieval.catalog",
        adapter_kind=None,
        model_id=None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.RETRIEVAL_ANSWER,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling", "correlation_and_audit"],
        ),
        authorization=authorization,
        generated_at="2026-03-24T00:00:00Z",
        stubbed=False,
        context_summary="Search Lotus knowledge sources",
        context_keys=["limit", "query", "source_ids"],
        source_refs=["lotus-workbench:knowledge-search:001"],
        result_preview="Catalog search completed.",
        structured_output={"provider_id": "retrieval.catalog"},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="access_control",
                    summary="Caller authorization recorded.",
                    attributes={"outcome": "ALLOWED"},
                )
            ]
        ),
    )

    repository.save(record)

    loaded = repository.get(
        "air_sql_authorized",
        scope=AuditReadScope.all_tenants(),
    )
    assert loaded is not None
    assert loaded.authorization == authorization


def test_sqlalchemy_audit_repository_handles_relative_sqlite_path(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    repository = SqlAlchemyAuditRepository("sqlite:///nested/db/audit.db")

    assert (tmp_path / "nested" / "db").is_dir()
    repository._engine.dispose()


def test_sqlalchemy_audit_repository_does_not_create_directory_for_memory_or_non_sqlite(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    SqlAlchemyAuditRepository("sqlite:///:memory:")._engine.dispose()

    configured_urls: list[str] = []

    def _fake_configure_sqlalchemy(self: SqlAlchemyAuditRepository, database_url: str) -> None:
        configured_urls.append(database_url)
        self._engine = type("Engine", (), {"dispose": lambda self: None})()

    monkeypatch.setattr(
        SqlAlchemyAuditRepository,
        "_configure_sqlalchemy",
        _fake_configure_sqlalchemy,
    )

    SqlAlchemyAuditRepository("postgresql://user:pass@localhost/db")._engine.dispose()

    assert not (tmp_path / "postgresql:").exists()
    assert configured_urls == ["postgresql://user:pass@localhost/db"]


def test_sqlalchemy_audit_repository_provider_defaults_cover_all_supported_modes() -> None:
    assert _default_provider_id("disabled") == "text.stub"
    assert _default_provider_id("stub") == "text.stub"
    assert _default_provider_id("openai") == "text.openai"
    assert _default_provider_id("local_openai_compatible") == "text.local"
    assert _default_provider_id("catalog_only") == "retrieval.catalog"
    assert _default_provider_id("catalog_answer") == "retrieval.answer"
    assert _default_provider_id("live_search") == "retrieval.live_search"
    assert _default_provider_id("unknown") == "unknown.provider"

    assert _default_adapter_kind("disabled") == ProviderAdapterKind.STUB
    assert _default_adapter_kind("stub") == ProviderAdapterKind.STUB
    assert _default_adapter_kind("openai") == ProviderAdapterKind.OPENAI_LIVE
    assert _default_adapter_kind("local_openai_compatible") == (
        ProviderAdapterKind.OPENAI_COMPATIBLE_LOCAL
    )
    assert _default_adapter_kind("catalog_only") is None
