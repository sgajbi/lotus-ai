from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.providers import (
    ROUTING_POLICY_FIXED_CONFIGURED_MODE,
    ROUTING_POLICY_VERSION_V1,
    ProviderExecutionMode,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderFailureCategory,
    RoutingCandidateDescriptor,
    RoutingDecisionDescriptor,
    RoutingStrategy,
)
from datetime import UTC, datetime

from app.contracts.model_catalogue import ModelCatalogueEntry
from app.providers.base import ProviderExecutionError
from app.providers.registry import resolve_text_generation_adapter
from app.services.access_control_authorization import authorize_request, require_authorized
from app.config import settings
from app.contracts.model_catalogue import derive_model_catalogue_entry_id
from app.services.kill_switch_control import enforce_kill_switches
from app.services.model_catalogue import bind_live_text_model_catalogue_entry
from app.services.provider_policy import require_supported_text_generation_mode
from app.services.provider_budget_policy import enforce_provider_budget, record_provider_spend
from app.services.provider_degradation_state import (
    enforce_provider_degradation_preflight,
    record_provider_failure,
    record_successful_provider_execution,
)
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_quota_policy import enforce_provider_quota


LIVE_TEXT_MODES = {
    ProviderExecutionMode.OPENAI,
    ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE,
}


class ProviderGatewayUnavailableError(HTTPException):
    """503 refusal that carries the routing decision behind the refusal."""

    def __init__(self, *, detail: str, routing_decision: RoutingDecisionDescriptor) -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
        self.routing_decision = routing_decision


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    mode = require_supported_text_generation_mode()
    live_execution_state = build_provider_live_execution_state(task_id=request.task_id)
    if mode in LIVE_TEXT_MODES and not live_execution_state.live_execution_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED.value}: "
                f"{live_execution_state.blocking_reason}"
            ),
        )
    catalogue_entry: ModelCatalogueEntry | None = None
    if mode in LIVE_TEXT_MODES:
        require_authorized(
            authorize_request(
                caller_app=request.caller_app,
                capability_type=AuthorizationCapabilityType.LIVE_PROVIDER_EXECUTION,
                tenant_id=request.tenant_id,
                task_id=request.task_id,
            )
        )
        try:
            # An operator kill switch outranks every automatic control.
            enforce_kill_switches(request)
            enforce_provider_quota(request)
            enforce_provider_budget()
            enforce_provider_degradation_preflight()
            catalogue_entry = bind_live_text_model_catalogue_entry()
        except ProviderExecutionError as exc:
            # A preflight veto is a candidate rejection: the decision records
            # the one configured candidate as rejected with the bounded
            # category, and no selection.
            raise ProviderGatewayUnavailableError(
                detail=f"{exc.category.value}: {exc.message}",
                routing_decision=_build_rejected_routing_decision(
                    mode_value=mode.value,
                    category=exc.category,
                ),
            ) from exc
    adapter = resolve_text_generation_adapter(mode)
    decided_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        response = adapter.execute(request)
        if catalogue_entry is not None:
            # Stamp the governed identity the execution was bound to; the
            # transport only knows settings strings and the provider echo.
            response.model_catalogue_entry_id = catalogue_entry.entry_id
            response.model_revision_pinned = catalogue_entry.revision_pinned
            if getattr(response, "model_version", None) is None:
                response.model_version = catalogue_entry.model_revision
        response.routing_decision = _build_fixed_routing_decision(
            mode_value=mode.value,
            selected_provider_id=response.provider_id,
            catalogue_entry=catalogue_entry,
            decided_at=decided_at,
        )
        if mode in LIVE_TEXT_MODES:
            record_provider_spend(response)
            record_successful_provider_execution()
        return response
    except ProviderExecutionError as exc:
        if mode in LIVE_TEXT_MODES:
            record_provider_failure(exc.category)
            # The candidate WAS selected; the provider then failed. The
            # decision records the selection - the failure itself is carried
            # by the failure category and evidence, not as a rejection.
            raise ProviderGatewayUnavailableError(
                detail=f"{exc.category.value}: {exc.message}",
                routing_decision=_build_fixed_routing_decision(
                    mode_value=mode.value,
                    selected_provider_id=settings.live_text_provider_id or "provider.unavailable",
                    catalogue_entry=catalogue_entry,
                    decided_at=decided_at,
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{exc.category.value}: {exc.message}",
        ) from exc


def _build_rejected_routing_decision(
    *,
    mode_value: str,
    category: ProviderFailureCategory,
) -> RoutingDecisionDescriptor:
    provider_id = settings.live_text_provider_id or "provider.unavailable"
    entry_id: str | None = None
    model_revision: str | None = None
    if settings.live_text_provider_id and settings.live_text_model_id:
        model_revision = settings.live_text_model_version or settings.live_text_model_id
        entry_id = derive_model_catalogue_entry_id(
            provider_id=settings.live_text_provider_id,
            model_revision=model_revision,
            deployment=None,
        )
    return RoutingDecisionDescriptor(
        policy_id=ROUTING_POLICY_FIXED_CONFIGURED_MODE,
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.FIXED,
        candidates=[
            RoutingCandidateDescriptor(
                provider_id=provider_id,
                provider_mode=mode_value,
                model_catalogue_entry_id=entry_id,
                model_revision=model_revision,
                rejection_reason=category,
            )
        ],
        selected_provider_id=None,
        selected_model_catalogue_entry_id=None,
        decided_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        selection_reason=(
            f"Fixed policy: the single configured candidate was rejected "
            f"({category.value}); execution refused."
        ),
    )


def _build_fixed_routing_decision(
    *,
    mode_value: str,
    selected_provider_id: str,
    catalogue_entry: ModelCatalogueEntry | None,
    decided_at: str,
) -> RoutingDecisionDescriptor:
    entry_id = catalogue_entry.entry_id if catalogue_entry is not None else None
    return RoutingDecisionDescriptor(
        policy_id=ROUTING_POLICY_FIXED_CONFIGURED_MODE,
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.FIXED,
        candidates=[
            RoutingCandidateDescriptor(
                provider_id=selected_provider_id,
                provider_mode=mode_value,
                model_catalogue_entry_id=entry_id,
                model_revision=(
                    catalogue_entry.model_revision if catalogue_entry is not None else None
                ),
            )
        ],
        selected_provider_id=selected_provider_id,
        selected_model_catalogue_entry_id=entry_id,
        decided_at=decided_at,
        selection_reason=(
            f"Fixed policy: configured provider mode '{mode_value}' resolves to exactly "
            "one adapter; no alternative candidates exist under this policy."
        ),
    )
