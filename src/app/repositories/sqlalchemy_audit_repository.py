from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.sql import Select

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.audit import AuditRecordResponse
from app.contracts.output_validation import OutputValidationOutcome
from app.contracts.audit_access import (
    AuditAccessDenialReason,
    AuditAccessEvent,
    AuditAccessOperation,
    AuditAccessOutcome,
    AuditReadScope,
    AuditReadScopeMode,
)
from app.contracts.evidence import ExecutionEvidenceBundle
from app.contracts.prompts import (
    PromptRolloutRole,
    PromptSelectionTraceDescriptor,
)
from app.contracts.providers import ProviderAdapterKind, RoutingDecisionDescriptor
from app.contracts.safety import RedactionPosture, SafetyExecutionOutcome
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.db.models import AuditAccessEventModel, AuditRecordModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.services.safety_runtime import build_safety_execution_outcome_from_record


class SqlAlchemyAuditRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def save(self, record: AuditRecordResponse) -> None:
        model = AuditRecordModel(
            request_id=record.request_id,
            execution_status=record.execution_status.value,
            task_id=record.task_id,
            category=record.category.value,
            output_label=record.output_label.value,
            caller_app=record.caller_app,
            correlation_id=record.correlation_id,
            requested_by=record.requested_by,
            tenant_id=record.tenant_id,
            prompt_version=record.prompt_version,
            prompt_selection_payload=record.prompt_selection.model_dump(mode="json"),
            provider_mode=record.provider_mode,
            provider_id=record.provider_id,
            adapter_kind=record.adapter_kind.value if record.adapter_kind is not None else None,
            model_id=record.model_id,
            model_version=record.model_version,
            model_catalogue_entry_id=record.model_catalogue_entry_id,
            model_revision_pinned=record.model_revision_pinned,
            routing_decision_payload=(
                record.routing_decision.model_dump(mode="json")
                if record.routing_decision is not None
                else None
            ),
            prompt_content_sha256=record.prompt_content_sha256,
            sampling_payload=record.sampling_parameters,
            provider_config_sha256=record.provider_config_sha256,
            estimated_cost_usd=record.estimated_cost_usd,
            rate_card_ref=record.rate_card_ref,
            safety_mode=record.safety_mode,
            redaction_posture=record.redaction_posture.value,
            enforced_safety_controls=record.enforced_safety_controls,
            safety_outcome_payload=record.safety_outcome.model_dump(mode="json"),
            output_validation_payload=(
                record.output_validation.model_dump(mode="json")
                if record.output_validation is not None
                else None
            ),
            validation_state=(
                record.output_validation.validation_state.value
                if record.output_validation is not None
                else None
            ),
            authorization_payload=record.authorization.model_dump(mode="json"),
            generated_at=record.generated_at,
            stubbed=record.stubbed,
            context_summary=record.context_summary,
            context_keys=record.context_keys,
            source_refs=record.source_refs,
            result_preview=record.result_preview,
            structured_output=record.structured_output,
            evidence=record.evidence.model_dump(mode="json"),
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def get(self, request_id: str, *, scope: AuditReadScope) -> AuditRecordResponse | None:
        with self._session_factory() as session:
            statement = select(AuditRecordModel).where(AuditRecordModel.request_id == request_id)
            statement = _apply_scope(statement, scope)
            model = session.execute(statement).scalar_one_or_none()
            if model is None:
                return None
            return self._to_contract(model)

    def list(
        self,
        *,
        caller_app: str | None = None,
        task_id: str | None = None,
        category: str | None = None,
        output_label: str | None = None,
        requested_by: str | None = None,
        scope: AuditReadScope,
        limit: int = 20,
    ) -> list[AuditRecordResponse]:
        statement = (
            select(AuditRecordModel).order_by(AuditRecordModel.generated_at.desc()).limit(limit)
        )
        statement = _apply_scope(statement, scope)
        if caller_app is not None:
            statement = statement.where(AuditRecordModel.caller_app == caller_app)
        if task_id is not None:
            statement = statement.where(AuditRecordModel.task_id == task_id)
        if category is not None:
            statement = statement.where(AuditRecordModel.category == category)
        if output_label is not None:
            statement = statement.where(AuditRecordModel.output_label == output_label)
        if requested_by is not None:
            statement = statement.where(AuditRecordModel.requested_by == requested_by)
        with self._session_factory() as session:
            models = session.execute(statement).scalars().all()
            return [self._to_contract(model) for model in models]

    def save_access_event(self, event: AuditAccessEvent) -> None:
        model = AuditAccessEventModel(
            event_id=event.event_id,
            caller_app=event.caller_app,
            caller_trust_source=event.caller_trust_source,
            scope_mode=event.scope_mode.value,
            operation=event.operation.value,
            outcome=event.outcome.value,
            denial_reason=event.denial_reason.value if event.denial_reason else None,
            returned_record_count=event.returned_record_count,
            recorded_at=event.recorded_at,
        )
        with self._session_factory() as session:
            session.add(model)
            session.commit()

    def list_access_events(self, *, limit: int = 100) -> Sequence[AuditAccessEvent]:
        statement = (
            select(AuditAccessEventModel)
            .order_by(AuditAccessEventModel.recorded_at.desc())
            .limit(limit)
        )
        with self._session_factory() as session:
            models = session.execute(statement).scalars().all()
            return [
                AuditAccessEvent(
                    event_id=model.event_id,
                    caller_app=model.caller_app,
                    caller_trust_source=model.caller_trust_source,
                    scope_mode=AuditReadScopeMode(model.scope_mode),
                    operation=AuditAccessOperation(model.operation),
                    outcome=AuditAccessOutcome(model.outcome),
                    denial_reason=(
                        AuditAccessDenialReason(model.denial_reason)
                        if model.denial_reason
                        else None
                    ),
                    returned_record_count=model.returned_record_count,
                    recorded_at=model.recorded_at,
                )
                for model in models
            ]

    def _to_contract(self, model: AuditRecordModel) -> AuditRecordResponse:
        output_label = OutputLabel(model.output_label)
        redaction_posture = RedactionPosture(model.redaction_posture)
        if model.provider_id:
            # Rows written since #175 S2b carry first-class identity columns.
            provider_id = model.provider_id
            adapter_kind = ProviderAdapterKind(model.adapter_kind) if model.adapter_kind else None
            model_id = model.model_id
        else:
            # Legacy rows predate the columns: recover identity from the stored
            # JSON payloads (best effort, mode-inferred defaults as a last resort).
            provider_id, adapter_kind, model_id = _build_provider_identity(model)
        safety_outcome = (
            SafetyExecutionOutcome.model_validate(model.safety_outcome_payload)
            if model.safety_outcome_payload is not None
            else build_safety_execution_outcome_from_record(
                safety_mode=model.safety_mode,
                output_label=output_label,
                redaction_posture=redaction_posture,
                enforced_controls=model.enforced_safety_controls,
            )
        )
        return AuditRecordResponse(
            request_id=model.request_id,
            execution_status=TaskExecutionStatus(model.execution_status),
            task_id=model.task_id,
            category=TaskCategory(model.category),
            output_label=output_label,
            caller_app=model.caller_app,
            correlation_id=model.correlation_id,
            requested_by=model.requested_by,
            tenant_id=model.tenant_id,
            prompt_version=model.prompt_version,
            prompt_selection=(
                PromptSelectionTraceDescriptor.model_validate(model.prompt_selection_payload)
                if model.prompt_selection_payload is not None
                else _build_legacy_prompt_selection(model)
            ),
            provider_mode=model.provider_mode,
            provider_id=provider_id,
            adapter_kind=adapter_kind,
            model_id=model_id,
            model_version=model.model_version,
            model_catalogue_entry_id=model.model_catalogue_entry_id,
            model_revision_pinned=model.model_revision_pinned,
            routing_decision=(
                RoutingDecisionDescriptor.model_validate(model.routing_decision_payload)
                if model.routing_decision_payload is not None
                else None
            ),
            prompt_content_sha256=model.prompt_content_sha256,
            sampling_parameters=model.sampling_payload,
            provider_config_sha256=model.provider_config_sha256,
            estimated_cost_usd=model.estimated_cost_usd,
            rate_card_ref=model.rate_card_ref,
            safety_mode=model.safety_mode,
            redaction_posture=redaction_posture,
            enforced_safety_controls=model.enforced_safety_controls,
            safety_outcome=safety_outcome,
            output_validation=(
                OutputValidationOutcome.model_validate(model.output_validation_payload)
                if model.output_validation_payload is not None
                else None
            ),
            authorization=(
                AuthorizationDecision.model_validate(model.authorization_payload)
                if model.authorization_payload is not None
                else _build_legacy_authorization(model)
            ),
            generated_at=model.generated_at,
            stubbed=model.stubbed,
            context_summary=model.context_summary,
            context_keys=model.context_keys,
            source_refs=model.source_refs,
            result_preview=model.result_preview,
            structured_output=model.structured_output,
            evidence=ExecutionEvidenceBundle.model_validate(model.evidence),
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        db_path = self._database_url.removeprefix(prefix)
        if db_path == ":memory:":
            return
        path = Path(db_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)


def _build_legacy_prompt_selection(model: AuditRecordModel) -> PromptSelectionTraceDescriptor:
    return PromptSelectionTraceDescriptor(
        task_id=model.task_id,
        prompt_version=model.prompt_version,
        rollout_role=PromptRolloutRole.ACTIVE,
        selection_reason=(
            "Legacy audit record preserved only the selected prompt version before prompt "
            "rollout trace payloads were added."
        ),
        active_prompt_version=model.prompt_version,
        candidate_prompt_version=None,
        previous_active_prompt_version=None,
        latest_control_event=None,
    )


def _build_legacy_authorization(model: AuditRecordModel) -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app=model.caller_app,
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=model.task_id,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=model.tenant_id,
        summary=(
            "Legacy audit record predates explicit caller authorization payload capture and is "
            "treated as an allowed task execution record."
        ),
    )


def _build_provider_identity(
    model: AuditRecordModel,
) -> tuple[str, ProviderAdapterKind | None, str | None]:
    structured_output = model.structured_output if isinstance(model.structured_output, dict) else {}
    evidence_bundle = ExecutionEvidenceBundle.model_validate(model.evidence)
    provider_descriptor = next(
        (
            descriptor
            for descriptor in evidence_bundle.descriptors
            if descriptor.evidence_type == "provider_resolution"
        ),
        None,
    )
    provider_id = structured_output.get("provider_id")
    if not isinstance(provider_id, str) or not provider_id:
        provider_id = (
            provider_descriptor.attributes.get("provider_id")
            if provider_descriptor is not None
            else None
        )
    if not isinstance(provider_id, str) or not provider_id:
        provider_id = _default_provider_id(model.provider_mode)
    adapter_kind_value = structured_output.get("adapter_kind")
    if not isinstance(adapter_kind_value, str) or not adapter_kind_value:
        adapter_kind_value = (
            provider_descriptor.attributes.get("adapter_kind")
            if provider_descriptor is not None
            else None
        )
    adapter_kind = (
        ProviderAdapterKind(adapter_kind_value)
        if isinstance(adapter_kind_value, str) and adapter_kind_value
        else _default_adapter_kind(model.provider_mode)
    )
    model_id_value = structured_output.get("model_id")
    if not isinstance(model_id_value, str) or not model_id_value:
        model_id_value = (
            provider_descriptor.attributes.get("model_id")
            if provider_descriptor is not None
            else None
        )
    model_id = model_id_value if isinstance(model_id_value, str) and model_id_value else None
    return provider_id, adapter_kind, model_id


def _default_provider_id(provider_mode: str) -> str:
    if provider_mode in {"disabled", "stub"}:
        return "text.stub"
    if provider_mode == "openai":
        return "text.openai"
    if provider_mode == "local_openai_compatible":
        return "text.local"
    if provider_mode == "catalog_only":
        return "retrieval.catalog"
    if provider_mode == "catalog_answer":
        return "retrieval.answer"
    if provider_mode == "live_search":
        return "retrieval.live_search"
    return "unknown.provider"


def _default_adapter_kind(provider_mode: str) -> ProviderAdapterKind | None:
    if provider_mode in {"disabled", "stub"}:
        return ProviderAdapterKind.STUB
    if provider_mode == "openai":
        return ProviderAdapterKind.OPENAI_LIVE
    if provider_mode == "local_openai_compatible":
        return ProviderAdapterKind.OPENAI_COMPATIBLE_LOCAL
    return None


def _apply_scope(
    statement: Select[tuple[AuditRecordModel]],
    scope: AuditReadScope,
) -> Select[tuple[AuditRecordModel]]:
    if scope.mode == AuditReadScopeMode.ALL_TENANTS:
        return statement
    return statement.where(AuditRecordModel.tenant_id.in_(sorted(scope.tenant_ids)))
