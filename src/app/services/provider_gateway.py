from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.providers import (
    ROUTING_POLICY_FIXED_CONFIGURED_MODE,
    ROUTING_POLICY_ORDERED_FALLBACK,
    ROUTING_POLICY_VERSION_V1,
    ProviderExecutionMode,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderFailureCategory,
    RoutingCandidateDescriptor,
    RoutingDecisionDescriptor,
    RoutingStrategy,
)
import time
from datetime import UTC, datetime

from app.contracts.model_catalogue import ModelCatalogueEntry
from app.providers.base import ProviderExecutionError
from app.providers.registry import resolve_text_generation_adapter
from app.services.access_control_authorization import authorize_request, require_authorized
from app.contracts.model_catalogue import derive_model_catalogue_entry_id
from app.services.provider_execution_config import (
    ProviderExecutionConfig,
    derive_fallback_execution_config,
    fallback_configuration_findings,
    override_provider_execution_config,
    resolve_provider_execution_config,
)
from app.services.kill_switch_control import enforce_kill_switches
from app.contracts.capability_requirements import CapabilityRequirements
from app.services.model_catalogue import (
    ENFORCED_REQUIREMENT_DIMENSIONS,
    bind_live_text_model_catalogue_entry,
    enforce_capability_requirements,
    record_model_revision_drift,
)
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

# A fallback attempt is warranted only for transient upstream trouble - the
# same categories the degradation state machine tracks. Configuration and
# governance refusals are deterministic: the alternate would not change them.
_FALLBACK_TRIGGER_CATEGORIES = frozenset(
    {
        ProviderFailureCategory.PROVIDER_TIMEOUT,
        ProviderFailureCategory.PROVIDER_RATE_LIMITED,
        ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
    }
)


class ProviderGatewayUnavailableError(HTTPException):
    """503 refusal that carries the routing decision behind the refusal."""

    def __init__(self, *, detail: str, routing_decision: RoutingDecisionDescriptor) -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
        self.routing_decision = routing_decision


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    request = _apply_latency_ceiling(request)
    config = resolve_provider_execution_config()
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
    if mode in LIVE_TEXT_MODES and config.routing_strategy == "ordered_fallback":
        return _execute_ordered_fallback(request, mode=mode, config=config)
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
            enforce_capability_requirements(
                requirements=request.requirements, entry=catalogue_entry
            )
            _require_budget_remaining(request)
        except ProviderExecutionError as exc:
            # A preflight veto is a candidate rejection: the decision records
            # the one configured candidate as rejected with the bounded
            # category, and no selection.
            raise ProviderGatewayUnavailableError(
                detail=f"{exc.category.value}: {exc.message}",
                routing_decision=_build_rejected_routing_decision(
                    requirements=request.requirements,
                    mode_value=mode.value,
                    category=exc.category,
                    config=config,
                ),
            ) from exc
    adapter = resolve_text_generation_adapter(mode)
    decided_at = _utc_now_iso()
    try:
        response = adapter.execute(_request_for_attempt(request), config=config)
        if catalogue_entry is not None:
            # Stamp the governed identity the execution was bound to; the
            # transport only knows settings strings and the provider echo.
            response.model_catalogue_entry_id = catalogue_entry.entry_id
            response.model_revision_pinned = catalogue_entry.revision_pinned
            if getattr(response, "model_version", None) is None:
                response.model_version = catalogue_entry.model_revision
            record_model_revision_drift(
                entry=catalogue_entry,
                observed_model_id=getattr(response, "model_id", None),
            )
        response.routing_decision = _build_fixed_routing_decision(
            # Enforcement is only claimable where the gates actually ran: the
            # capability check needs a catalogue bind and the latency ceiling
            # bounds a provider wait, neither of which exists on the stub path.
            requirements=request.requirements if mode in LIVE_TEXT_MODES else None,
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
                    requirements=request.requirements,
                    mode_value=mode.value,
                    selected_provider_id=config.provider_id or "provider.unavailable",
                    catalogue_entry=catalogue_entry,
                    decided_at=decided_at,
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{exc.category.value}: {exc.message}",
        ) from exc


def _execute_ordered_fallback(
    request: ProviderExecutionRequest,
    *,
    mode: ProviderExecutionMode,
    config: ProviderExecutionConfig,
) -> ProviderExecutionResponse:
    """Ordered-fallback live execution (issue #176, S3).

    The candidate order is fixed: [primary, configured alternate]. The
    candidate-scoped controls - kill switches on provider/model scopes, the
    per-provider circuit breaker, and the catalogue bind - are evaluated per
    candidate under that candidate's execution-config override. The
    request-scoped economics - quota counters and the budget envelope - are
    enforced exactly once: a fallback never bypasses or double-charges them.
    """

    require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.LIVE_PROVIDER_EXECUTION,
            tenant_id=request.tenant_id,
            task_id=request.task_id,
        )
    )
    findings = fallback_configuration_findings(config)
    alternate = derive_fallback_execution_config(config)
    if findings or alternate is None:
        detail = "; ".join(findings) or (
            "ordered_fallback requires a complete fallback identity and none is configured"
        )
        raise ProviderGatewayUnavailableError(
            detail=f"{ProviderFailureCategory.INVALID_LIVE_CONFIGURATION.value}: {detail}",
            routing_decision=_build_ordered_routing_decision(
                requirements=request.requirements,
                mode_value=mode.value,
                candidates=[(config, ProviderFailureCategory.INVALID_LIVE_CONFIGURATION)],
                serving_config=None,
                serving_entry=None,
                fallback_path=[],
                decided_at=_utc_now_iso(),
            ),
        )

    rejections: dict[int, ProviderFailureCategory] = {}
    candidates = [config, alternate]

    # Operator kill switches outrank every automatic control, evaluated per
    # candidate: a switch on the primary's provider scope routes to the
    # alternate; a request-scoped switch (all-live-text, task, tenant,
    # caller) matches and rejects both candidates.
    eligible: list[int] = []
    veto_errors: list[ProviderExecutionError] = []
    for index, candidate in enumerate(candidates):
        try:
            with override_provider_execution_config(candidate):
                enforce_kill_switches(request)
        except ProviderExecutionError as exc:
            rejections[index] = exc.category
            veto_errors.append(exc)
            continue
        eligible.append(index)
    if not eligible:
        raise _ordered_refusal(
            requirements=request.requirements,
            error=veto_errors[-1],
            mode_value=mode.value,
            candidates=candidates,
            rejections=rejections,
            fallback_path=[],
        )

    try:
        enforce_provider_quota(request)
        enforce_provider_budget()
    except ProviderExecutionError as exc:
        for index in eligible:
            rejections[index] = exc.category
        raise _ordered_refusal(
            requirements=request.requirements,
            error=exc,
            mode_value=mode.value,
            candidates=candidates,
            rejections=rejections,
            fallback_path=[],
        ) from exc

    adapter = resolve_text_generation_adapter(mode)
    fallback_path: list[str] = []
    attempt_errors: list[ProviderExecutionError] = []
    for index in eligible:
        candidate = candidates[index]
        with override_provider_execution_config(candidate):
            try:
                # The governed deadline outranks fallback: an exhausted budget
                # rejects this candidate without an attempt, and the next
                # candidate's check rejects it too - the alternate never
                # starts after exhaustion, and the budget is never reset.
                _require_budget_remaining(request)
                enforce_provider_degradation_preflight()
                catalogue_entry = bind_live_text_model_catalogue_entry()
                enforce_capability_requirements(
                    requirements=request.requirements, entry=catalogue_entry
                )
            except ProviderExecutionError as exc:
                rejections[index] = exc.category
                attempt_errors.append(exc)
                continue
            try:
                response = adapter.execute(_request_for_attempt(request), config=candidate)
            except ProviderExecutionError as exc:
                record_provider_failure(exc.category)
                rejections[index] = exc.category
                attempt_errors.append(exc)
                if candidate.provider_id:
                    fallback_path.append(candidate.provider_id)
                if exc.category not in _FALLBACK_TRIGGER_CATEGORIES:
                    # Deterministic refusal: the alternate cannot change it.
                    break
                continue
            response.model_catalogue_entry_id = catalogue_entry.entry_id
            response.model_revision_pinned = catalogue_entry.revision_pinned
            if getattr(response, "model_version", None) is None:
                response.model_version = catalogue_entry.model_revision
            record_model_revision_drift(
                entry=catalogue_entry,
                observed_model_id=getattr(response, "model_id", None),
            )
            response.routing_decision = _build_ordered_routing_decision(
                requirements=request.requirements,
                mode_value=mode.value,
                candidates=[
                    (item, rejections.get(position)) for position, item in enumerate(candidates)
                ],
                serving_config=candidate,
                serving_entry=catalogue_entry,
                fallback_path=fallback_path,
                decided_at=_utc_now_iso(),
            )
            record_provider_spend(response)
            record_successful_provider_execution()
            return response

    # Every eligible candidate either returned above or appended its error.
    raise _ordered_refusal(
        requirements=request.requirements,
        error=attempt_errors[-1],
        mode_value=mode.value,
        candidates=candidates,
        rejections=rejections,
        fallback_path=fallback_path,
    )


def _ordered_refusal(
    *,
    error: ProviderExecutionError,
    requirements: CapabilityRequirements | None,
    mode_value: str,
    candidates: list[ProviderExecutionConfig],
    rejections: dict[int, ProviderFailureCategory],
    fallback_path: list[str],
) -> ProviderGatewayUnavailableError:
    return ProviderGatewayUnavailableError(
        detail=f"{error.category.value}: {error.message}",
        routing_decision=_build_ordered_routing_decision(
            requirements=requirements,
            mode_value=mode_value,
            candidates=[
                (candidate, rejections.get(index)) for index, candidate in enumerate(candidates)
            ],
            serving_config=None,
            serving_entry=None,
            fallback_path=fallback_path,
            decided_at=_utc_now_iso(),
        ),
    )


def _candidate_entry_identity(
    config: ProviderExecutionConfig,
) -> tuple[str | None, str | None]:
    if not (config.provider_id and config.model_id):
        return None, None
    model_revision = config.model_version or config.model_id
    entry_id = derive_model_catalogue_entry_id(
        provider_id=config.provider_id,
        model_revision=model_revision,
        deployment=None,
    )
    return entry_id, model_revision


def _build_ordered_routing_decision(
    *,
    requirements: CapabilityRequirements | None,
    mode_value: str,
    candidates: list[tuple[ProviderExecutionConfig, ProviderFailureCategory | None]],
    serving_config: ProviderExecutionConfig | None,
    serving_entry: ModelCatalogueEntry | None,
    fallback_path: list[str],
    decided_at: str,
) -> RoutingDecisionDescriptor:
    descriptors: list[RoutingCandidateDescriptor] = []
    for candidate, rejection in candidates:
        entry_id, model_revision = _candidate_entry_identity(candidate)
        descriptors.append(
            RoutingCandidateDescriptor(
                provider_id=candidate.provider_id or "provider.unavailable",
                provider_mode=mode_value,
                model_catalogue_entry_id=entry_id,
                model_revision=model_revision,
                rejection_reason=rejection,
            )
        )
    if serving_config is None:
        selection_reason = (
            "Ordered-fallback policy: every candidate was rejected or failed; execution refused."
        )
    elif fallback_path:
        selection_reason = (
            "Ordered-fallback policy: the primary candidate failed and the alternate "
            "candidate served; the fallback path names the failed provider(s)."
        )
    elif serving_config is candidates[0][0]:
        selection_reason = "Ordered-fallback policy: the primary candidate served."
    else:
        selection_reason = (
            "Ordered-fallback policy: the primary candidate was rejected at preflight and "
            "the alternate candidate served; a preflight rejection is not a fallback."
        )
    enforced_dimensions, unenforced_dimensions = _requirement_enforcement_split(requirements)
    return RoutingDecisionDescriptor(
        policy_id=ROUTING_POLICY_ORDERED_FALLBACK,
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.ORDERED_FALLBACK,
        candidates=descriptors,
        requirements_enforced_dimensions=enforced_dimensions,
        requirements_unenforced_dimensions=unenforced_dimensions,
        selected_provider_id=serving_config.provider_id if serving_config is not None else None,
        selected_model_catalogue_entry_id=(
            serving_entry.entry_id if serving_entry is not None else None
        ),
        decided_at=decided_at,
        selection_reason=selection_reason,
        fallback_path=fallback_path,
    )


def _apply_latency_ceiling(request: ProviderExecutionRequest) -> ProviderExecutionRequest:
    """Start the governed end-to-end latency budget (issue #244).

    `max_latency_ms` is one execution deadline, not an attempt timeout: a
    single monotonic deadline is stamped here, every later stage receives only
    the remaining budget, and nothing - retry, backoff sleep, or fallback -
    resets it. The first attempt's timeout is tightened to the budget; each
    subsequent attempt is tightened to what remains at its start.
    """

    requirements = request.requirements
    if requirements is None or requirements.max_latency_ms is None:
        return request
    return request.model_copy(
        update={
            "timeout_ms": min(request.timeout_ms, requirements.max_latency_ms),
            "execution_deadline_at": _monotonic() + requirements.max_latency_ms / 1000.0,
        }
    )


def _remaining_budget_ms(request: ProviderExecutionRequest) -> int | None:
    """Milliseconds left on the governed deadline; None when no budget is set.

    Zero means exhausted: the value is clamped, and callers treat <= 0 as
    "no further attempt may start".
    """

    if request.execution_deadline_at is None:
        return None
    return int((request.execution_deadline_at - _monotonic()) * 1000.0)


def _request_for_attempt(request: ProviderExecutionRequest) -> ProviderExecutionRequest:
    """The request an individual candidate attempt may execute.

    The attempt timeout is the smaller of the configured timeout and the
    remaining governed budget, so an attempt can never run past the deadline
    earlier stages already spent from.
    """

    remaining = _remaining_budget_ms(request)
    if remaining is None or remaining >= request.timeout_ms:
        return request
    return request.model_copy(update={"timeout_ms": max(remaining, 1)})


def _require_budget_remaining(request: ProviderExecutionRequest) -> None:
    remaining = _remaining_budget_ms(request)
    if remaining is not None and remaining <= 0:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.REQUEST_DEADLINE_EXHAUSTED,
            message=(
                "The caller's max_latency_ms budget is exhausted; no further provider "
                "attempt may start."
            ),
        )


def _requirement_enforcement_split(
    requirements: CapabilityRequirements | None,
) -> tuple[list[str], list[str]]:
    """Declared dimensions split into what this decision enforces and what it
    does not - so a declared ceiling can never silently pass for a held one."""

    if requirements is None:
        return ([], [])
    declared = requirements.declared_dimensions()
    enforced = sorted(set(declared) & ENFORCED_REQUIREMENT_DIMENSIONS)
    unenforced = sorted(set(declared) - ENFORCED_REQUIREMENT_DIMENSIONS)
    return (enforced, unenforced)


def _monotonic() -> float:
    """Seam for the governed-deadline clock; tests replace it."""

    return time.perf_counter()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_rejected_routing_decision(
    *,
    requirements: CapabilityRequirements | None,
    mode_value: str,
    category: ProviderFailureCategory,
    config: ProviderExecutionConfig,
) -> RoutingDecisionDescriptor:
    provider_id = config.provider_id or "provider.unavailable"
    entry_id, model_revision = _candidate_entry_identity(config)
    enforced_dimensions, unenforced_dimensions = _requirement_enforcement_split(requirements)
    return RoutingDecisionDescriptor(
        policy_id=ROUTING_POLICY_FIXED_CONFIGURED_MODE,
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.FIXED,
        requirements_enforced_dimensions=enforced_dimensions,
        requirements_unenforced_dimensions=unenforced_dimensions,
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
        decided_at=_utc_now_iso(),
        selection_reason=(
            f"Fixed policy: the single configured candidate was rejected "
            f"({category.value}); execution refused."
        ),
    )


def _build_fixed_routing_decision(
    *,
    requirements: CapabilityRequirements | None,
    mode_value: str,
    selected_provider_id: str,
    catalogue_entry: ModelCatalogueEntry | None,
    decided_at: str,
) -> RoutingDecisionDescriptor:
    entry_id = catalogue_entry.entry_id if catalogue_entry is not None else None
    enforced_dimensions, unenforced_dimensions = _requirement_enforcement_split(requirements)
    return RoutingDecisionDescriptor(
        policy_id=ROUTING_POLICY_FIXED_CONFIGURED_MODE,
        policy_version=ROUTING_POLICY_VERSION_V1,
        strategy=RoutingStrategy.FIXED,
        requirements_enforced_dimensions=enforced_dimensions,
        requirements_unenforced_dimensions=unenforced_dimensions,
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
