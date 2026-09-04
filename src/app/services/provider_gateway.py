from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.providers import (
    ROUTING_POLICY_FIXED_CONFIGURED_MODE,
    ROUTING_POLICY_ORDERED_FALLBACK,
    ROUTING_POLICY_VERSION_V1,
    CandidateUniverse,
    CandidateUniverseExclusionReason,
    CandidateUniverseSource,
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
from app.services.provider_connection_material import (
    connection_material_findings,
    derive_candidate_execution_config,
)
from app.contracts.capability_requirements import CapabilityRequirements
from app.services.model_catalogue import (
    ENFORCED_REQUIREMENT_DIMENSIONS,
    bind_live_text_model_catalogue_entry,
    derive_candidate_universe,
    enforce_capability_requirements,
    record_model_revision_drift,
)
from app.services.provider_policy import require_supported_text_generation_mode
from app.services.provider_budget_policy import enforce_provider_budget
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
        # The caller's cost ceiling refusing THIS candidate does not refuse
        # the execution: a cheaper alternate's own admission check may still
        # fit within the shared remaining ceiling (issue #290). The latency
        # budget differs deliberately - exhausted time is global.
        ProviderFailureCategory.REQUEST_COST_EXHAUSTED,
    }
)


class ProviderGatewayUnavailableError(HTTPException):
    """503 refusal that carries the routing decision behind the refusal."""

    def __init__(self, *, detail: str, routing_decision: RoutingDecisionDescriptor) -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
        self.routing_decision = routing_decision


def execute_text_generation(request: ProviderExecutionRequest) -> ProviderExecutionResponse:
    request = _apply_latency_ceiling(request)
    request = _apply_cost_ceiling(request)
    if request.execution_id is None:
        # One identity per execution, shared by every retry and fallback
        # candidate: attempt debits key on it (issue #289).
        request = request.model_copy(update={"execution_id": uuid4().hex})
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
    execution_config = config
    if mode in LIVE_TEXT_MODES:
        require_authorized(
            authorize_request(
                caller_app=request.caller_app,
                capability_type=AuthorizationCapabilityType.LIVE_PROVIDER_EXECUTION,
                tenant_id=request.tenant_id,
                task_id=request.task_id,
            )
        )
        material_findings = connection_material_findings()
        if material_findings:
            # Malformed declared material means the platform cannot know
            # whether the serving identity's connection is overridden -
            # serving anyway could use stale connection truth, so the fixed
            # path fails closed exactly as the ordered path does (#298).
            raise ProviderGatewayUnavailableError(
                detail=(
                    f"{ProviderFailureCategory.INVALID_LIVE_CONFIGURATION.value}: "
                    + "; ".join(material_findings)
                ),
                routing_decision=_build_rejected_routing_decision(
                    requirements=request.requirements,
                    mode_value=mode.value,
                    category=ProviderFailureCategory.INVALID_LIVE_CONFIGURATION,
                    config=config,
                ),
            )
        primary_entry_id, _ = _candidate_entry_identity(config)
        if primary_entry_id is not None:
            # One connection authority (issue #298): the fixed path serves
            # the primary identity, so its execution config resolves through
            # the same merged material seam the ordered path enumerates from
            # - a declared override of the primary drives the actual call.
            resolved = derive_candidate_execution_config(config, primary_entry_id)
            if resolved is not None:
                execution_config = resolved
        try:
            # An operator kill switch outranks every automatic control.
            enforce_kill_switches(request)
            enforce_provider_quota(request)
            enforce_provider_budget()
            enforce_provider_degradation_preflight()
            catalogue_entry = bind_live_text_model_catalogue_entry()
            enforce_capability_requirements(
                requirements=request.requirements,
                entry=catalogue_entry,
                output_contract_key=request.output_contract_key,
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
        response = adapter.execute(_request_for_attempt(request), config=execution_config)
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
            # Spend was debited durably at each attempt boundary (issue
            # #289); the response merely projects those debits.
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
    findings = fallback_configuration_findings(config) + connection_material_findings()
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

    # The derived universe IS the enumeration (issue #244, U2): the configured
    # pair supplies policy order and connection material, and the catalogue
    # decides which of those identities may serve at all. An identity the
    # catalogue excludes never becomes a candidate - its reasoned exclusion
    # rides the routing decision instead.
    universe = derive_candidate_universe(config)
    # Connection material resolves per governed identity (issue #295 S1,
    # #298): the merged material map is the one connection authority - an
    # untouched pair resolves to exactly the configs it always did, and a
    # declared override IS the config the candidate executes under.
    candidates = [
        candidate
        for entry_id in universe.candidate_entry_ids
        if (candidate := derive_candidate_execution_config(config, entry_id)) is not None
    ]
    if not candidates:
        raise _empty_universe_refusal(
            requirements=request.requirements, mode_value=mode.value, universe=universe
        )
    rejections: dict[int, ProviderFailureCategory] = {}

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
            universe=universe,
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
            universe=universe,
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
                    requirements=request.requirements,
                    entry=catalogue_entry,
                    output_contract_key=request.output_contract_key,
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
                universe=universe,
            )
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
        universe=universe,
    )


def _ordered_refusal(
    *,
    error: ProviderExecutionError,
    requirements: CapabilityRequirements | None,
    mode_value: str,
    candidates: list[ProviderExecutionConfig],
    rejections: dict[int, ProviderFailureCategory],
    fallback_path: list[str],
    universe: CandidateUniverse | None = None,
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
            universe=universe,
        ),
    )


_FAILURE_BY_UNIVERSE_EXCLUSION = {
    CandidateUniverseExclusionReason.MODEL_NOT_CATALOGUED: (
        ProviderFailureCategory.MODEL_NOT_CATALOGUED
    ),
    CandidateUniverseExclusionReason.LIFECYCLE_INELIGIBLE: (
        ProviderFailureCategory.MODEL_LIFECYCLE_INELIGIBLE
    ),
    CandidateUniverseExclusionReason.POLICY_EXCLUDED: (
        ProviderFailureCategory.INVALID_LIVE_CONFIGURATION
    ),
}


def _empty_universe_refusal(
    *,
    requirements: CapabilityRequirements | None,
    mode_value: str,
    universe: CandidateUniverse,
) -> ProviderGatewayUnavailableError:
    """No policy-ordered identity earned eligibility: refuse with every reason.

    The category comes from the first policy-identity exclusion so the caller
    sees the primary story; the decision carries all of them.
    """

    category = next(
        (
            _FAILURE_BY_UNIVERSE_EXCLUSION[exclusion.reason]
            for exclusion in universe.exclusions
            if exclusion.reason is not CandidateUniverseExclusionReason.POLICY_EXCLUDED
        ),
        ProviderFailureCategory.INVALID_LIVE_CONFIGURATION,
    )
    detail = "; ".join(exclusion.detail for exclusion in universe.exclusions) or (
        "the derived candidate universe is empty"
    )
    return ProviderGatewayUnavailableError(
        detail=f"{category.value}: {detail}",
        routing_decision=_build_ordered_routing_decision(
            requirements=requirements,
            mode_value=mode_value,
            candidates=[],
            serving_config=None,
            serving_entry=None,
            fallback_path=[],
            decided_at=_utc_now_iso(),
            universe=universe,
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
    universe: CandidateUniverse | None = None,
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
    if serving_config is None and not candidates:
        selection_reason = (
            "Ordered-fallback policy: the derived candidate universe is empty - every "
            "policy-ordered identity was excluded (see universe_exclusions); execution refused."
        )
    elif serving_config is None:
        selection_reason = (
            "Ordered-fallback policy: every candidate was rejected or failed; execution refused."
        )
    elif fallback_path:
        selection_reason = (
            "Ordered-fallback policy: an earlier candidate failed and a later candidate "
            "served; the fallback path names the failed provider(s)."
        )
    elif serving_config is candidates[0][0]:
        # "First enumerated", not "primary": the universe may have excluded
        # the configured primary, and the evidence must not claim it served.
        selection_reason = (
            "Ordered-fallback policy: the first candidate in the enumerated universe served."
        )
    else:
        selection_reason = (
            "Ordered-fallback policy: an earlier candidate was rejected at preflight and "
            "a later candidate served; a preflight rejection is not a fallback."
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
        universe_source=(
            universe.source if universe is not None else CandidateUniverseSource.CONFIGURED
        ),
        universe_exclusions=list(universe.exclusions) if universe is not None else [],
        serving_policy_version=(universe.serving_policy_version if universe is not None else None),
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


def _apply_cost_ceiling(request: ProviderExecutionRequest) -> ProviderExecutionRequest:
    """Start the governed execution cost budget (issue #290).

    `max_estimated_cost_usd` is one execution ceiling, not an attempt price:
    it is stamped once here, every retry and fallback candidate consumes
    from it through the durable attempt debits, and nothing resets it - the
    latency budget's own design, applied to money.
    """

    requirements = request.requirements
    if requirements is None or requirements.max_estimated_cost_usd is None:
        return request
    return request.model_copy(update={"cost_ceiling_usd": requirements.max_estimated_cost_usd})


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
