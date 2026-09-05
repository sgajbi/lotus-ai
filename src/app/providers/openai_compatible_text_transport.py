from __future__ import annotations

import json
import logging
import time
from typing import Any, cast
from urllib import error, request as urllib_request
from uuid import uuid4

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderExecutionMode,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
    ProviderFailureCategory,
)
from app.contracts.model_catalogue import (
    derive_candidate_identity_v2,
    derive_model_catalogue_entry_id,
)
from app.providers.base import ProviderAdapterDescriptor, ProviderExecutionError
from app.services.provider_execution_overrides import (
    ensure_network_execution_permitted,
    get_text_transport_post_override,
)
from app.services.provider_metrics import record_provider_attempt
from app.services.provider_retry_backoff import (
    RetryBackoffPlan,
    plan_retry,
    wait_for_retry,
)
from app.services.tracing_runtime import (
    inject_trace_context,
    provider_attempt_span,
    record_provider_span_outcome,
)
from app.services.structured_logging import correlation_id_var, log_event
from app.providers.openai_response_parsing import (
    as_int,
    as_str,
    parse_json_object_with_posture,
)
from app.providers.advisor_brief_quality_guardrails import (
    build_advisor_brief_user_message,
    normalize_advisor_brief_output,
)
from app.providers.idea_explanation_quality_guardrails import (
    is_idea_explanation_payload,
    normalize_idea_explanation_output,
)
from app.services.provider_budget_policy import (
    require_priceable_admission,
    reserve_attempt_spend,
    settle_attempt_spend,
    spent_for_execution,
)
from app.services.provider_usage_accounting import (
    AttemptDebit,
    estimate_live_text_cost,
    price_attempt,
    project_attempt_billing,
)


def execute_openai_compatible_text_request(
    *,
    descriptor: ProviderAdapterDescriptor,
    request: ProviderExecutionRequest,
    api_base: str,
    api_key: str | None,
    require_api_key: bool,
    model_id: str | None,
    model_version: str | None,
    provider_id: str | None = None,
    deployment: str | None = None,
) -> ProviderExecutionResponse:
    # The serving identity is the execution config's provider id (issues
    # #226, #237): under ordered fallback both candidates run through the
    # same adapter, so the static descriptor constants would attribute the
    # alternate's executions to the primary on every surface naming a
    # provider.
    serving_provider_id = provider_id or descriptor.provider_id
    payload: dict[str, object] = {
        "model": model_id,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"{request.system_instructions}\n\n"
                            f"Output contract notes:\n{request.output_contract_notes}"
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": build_user_message(request)}],
            },
        ],
        "max_output_tokens": request.max_output_tokens,
        "temperature": request.temperature,
    }
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.seed is not None:
        payload["seed"] = request.seed
    response_payload = post_openai_compatible_response(
        api_base=api_base,
        api_key=api_key,
        payload=payload,
        timeout_seconds=max(request.timeout_ms / 1000.0, 1.0),
        serving_provider_id=serving_provider_id,
        require_api_key=require_api_key,
        retry_limit=request.retry_limit,
        execution_deadline_at=request.execution_deadline_at,
        execution_id=request.execution_id,
        cost_posture=request.failed_attempt_cost_posture,
        model_revision=model_version or model_id,
        cost_ceiling_usd=request.cost_ceiling_usd,
        deployment=deployment,
        model_family=model_id,
    )
    output_message = extract_output_text(response_payload)
    message, structured_output = build_structured_output(
        descriptor=descriptor,
        request=request,
        response_payload=response_payload,
        output_message=output_message,
        configured_model_id=model_id,
        provider_id=serving_provider_id,
    )
    input_tokens, output_tokens, total_tokens = extract_usage(response_payload)
    cost = estimate_live_text_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_revision=model_version or model_id,
    )
    # The response projects the durable attempt debits (issue #289): the
    # failed-attempt figures are exactly what the boundary recorded, and the
    # served attempt's cost equals its own boundary debit by construction
    # (same usage, same rate card).
    billing = project_attempt_billing(
        final_cost=cost,
        failed_debits=extract_failed_attempt_debits(response_payload),
        had_failed_attempts=bool(extract_failed_attempts(response_payload)),
    )
    return ProviderExecutionResponse(
        provider_id=serving_provider_id,
        provider_mode=descriptor.runtime_mode.value,
        adapter_kind=descriptor.adapter_kind,
        failure_category=None,
        timeout_ms=request.timeout_ms,
        retry_count=extract_retry_count(response_payload),
        max_output_tokens=request.max_output_tokens,
        model_id=as_str(response_payload.get("model")) or model_id,
        model_version=model_version,
        provider_request_id=as_str(response_payload.get("id")),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=billing.estimated_cost_usd,
        failed_attempt_cost_usd=billing.failed_attempt_cost_usd,
        failed_attempt_cost_basis=billing.failed_attempt_cost_basis,
        billed_attempt_count=billing.billed_attempt_count,
        rate_card_ref=cost.rate_card_ref,
        stubbed=False,
        message=message,
        structured_output=structured_output,
    )


def build_user_message(request: ProviderExecutionRequest) -> str:
    if is_advisor_brief_payload(request.context_payload):
        return build_advisor_brief_user_message(
            task_id=request.task_id,
            caller_app=request.caller_app,
            context_summary=request.context_summary,
            context_payload=request.context_payload,
            source_refs=request.source_refs,
        )
    return json.dumps(
        {
            "task_id": request.task_id,
            "caller_app": request.caller_app,
            "context_summary": request.context_summary,
            "context_payload": request.context_payload,
            "source_refs": request.source_refs,
        },
        indent=2,
        sort_keys=True,
    )


def post_openai_compatible_response(
    *,
    api_base: str,
    api_key: str | None,
    payload: dict[str, object],
    timeout_seconds: float,
    serving_provider_id: str,
    require_api_key: bool,
    retry_limit: int = 0,
    execution_deadline_at: float | None = None,
    execution_id: str | None = None,
    cost_posture: str = "conservative",
    model_revision: str | None = None,
    cost_ceiling_usd: float | None = None,
    deployment: str | None = None,
    model_family: str | None = None,
) -> dict[str, Any]:
    """POST one OpenAI-compatible request, labelling every surface it emits
    with ``serving_provider_id``.

    This used to take the descriptor's display name. Under ordered fallback
    both candidates run through the same adapter, so the display name is
    structurally unable to say which one served: it names the adapter, not
    the candidate. Metrics, logs, spans, and bounded failure messages all
    take the execution config's provider id instead, which is the identity
    the audit record, routing decision, breaker key, and kill switch
    already use (issue #237).
    """

    override = get_text_transport_post_override()
    if override is not None:
        return override(
            api_base=api_base,
            api_key=api_key,
            payload=payload,
            timeout_seconds=timeout_seconds,
            serving_provider_id=serving_provider_id,
            require_api_key=require_api_key,
            retry_limit=retry_limit,
        )
    if require_api_key and api_key is None:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_LIVE_CONFIGURATION,
            message=f"Live provider credentials are not configured for {serving_provider_id}.",
        )
    ensure_network_execution_permitted(
        seam="openai_compatible_text_transport.post_openai_compatible_response"
    )
    endpoint = api_base.rstrip("/") + "/responses"
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    correlation_id = correlation_id_var.get()
    if correlation_id is not None:
        headers["X-Correlation-Id"] = correlation_id
    inject_trace_context(headers)
    model_identity = payload.get("model")
    bounded_retry_limit = max(retry_limit, 0)
    backoff_plan = RetryBackoffPlan(
        timeout_seconds=timeout_seconds, retry_limit=bounded_retry_limit
    )
    # The retry sequence is bounded by its own plan AND, when the caller
    # declared max_latency_ms, by the governed execution deadline - whichever
    # comes first. The governed deadline is never extended here (issue #244).
    deadline_at = _monotonic() + backoff_plan.total_deadline_seconds
    if execution_deadline_at is not None:
        deadline_at = min(deadline_at, execution_deadline_at)
    # Usage evidence for each failed attempt that precedes the served one
    # (issue #232): the provider may have generated and billed before failing,
    # so the billing settlement needs what each attempt is known to have used.
    failed_attempts: list[dict[str, object]] = []
    # Every potentially billable attempt debits durable spend AT ITS OWN
    # BOUNDARY (issue #289) - the identity below keys the idempotent debit,
    # so an execution that never succeeds, falls back, or dies later has
    # already moved the budget envelope. Without a gateway-minted identity
    # (direct callers) the transport mints one: production attempts always
    # debit.
    debit_execution_id = execution_id or uuid4().hex
    # The debit identity segment is the CANDIDATE - the catalogue entry id
    # binding provider, model revision and deployment (issue #299) - because
    # two model candidates at the same provider are normal serving topology
    # and a provider-keyed identity would collide their attempt debits. A
    # caller that supplies no model revision cannot name a candidate; its
    # debits key by provider honestly (and record no candidate identity).
    candidate_entry_id = (
        derive_model_catalogue_entry_id(
            provider_id=serving_provider_id,
            model_revision=model_revision,
            deployment=deployment,
        )
        if model_revision
        else serving_provider_id
    )
    # Resolvable canonical reference on new debit evidence (issue #314):
    # the debit_id keeps its v1-shaped idempotency identity; the canonical
    # id rides alongside when the caller names a complete candidate.
    candidate_id_v2 = (
        derive_candidate_identity_v2(
            provider_id=serving_provider_id,
            model_family=model_family,
            model_revision=model_revision,
            deployment=deployment,
        )
        if model_revision and model_family
        else None
    )
    # Conservative input estimate for attempts that never revealed usage:
    # the request body is hard evidence of what was sent; ~4 bytes/token is
    # the documented approximation, replaced by provider-reported input
    # tokens the moment any attempt in this execution reveals them.
    input_estimate = max(1, len(body) // 4)
    payload_max_output = as_int(payload.get("max_output_tokens")) or 0

    def _debit_boundary(
        *,
        attempt_index: int,
        input_tokens: int | None,
        output_tokens: int | None,
        billable_risk: bool,
    ) -> AttemptDebit | None:
        """Settle this attempt's pre-attempt reservation to its evidenced
        debit (issue #300): actual usage, the conservative estimate for a
        billable-risk failure, or a zero-amount release when the attempt
        proved non-billable (429, pre-connect). Non-billability is STATED
        via ``billable_risk`` (issue #346), never inferred from pricing
        availability: a billable-risk attempt whose settle-time pricing
        returns None (rate card expired mid-attempt) holds its reserved
        maximum instead of releasing."""

        debit = price_attempt(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            billable_risk=billable_risk,
            posture=cost_posture,
            fallback_input_estimate=input_estimate,
            max_output_tokens=payload_max_output,
            model_revision=model_revision,
        )
        if debit is None and billable_risk and input_tokens is not None:
            # Served (or usage-revealing) attempt that cannot be priced: the
            # observed usage is operator evidence for the governed
            # reconciliation that will settle the held exposure.
            log_event(
                _logger,
                "attempt_exposure_held_unpriceable",
                execution_id=debit_execution_id,
                attempt_index=attempt_index,
                observed_input_tokens=input_tokens,
                observed_output_tokens=output_tokens,
            )
        settle_attempt_spend(
            execution_id=debit_execution_id,
            candidate_entry_id=candidate_entry_id,
            attempt_index=attempt_index,
            debit=debit,
            candidate_id_v2=candidate_id_v2,
            billable_risk=billable_risk,
        )
        return debit

    for attempt_index in range(bounded_retry_limit + 1):
        if execution_deadline_at is not None:
            remaining_seconds = execution_deadline_at - _monotonic()
            if remaining_seconds <= 0:
                raise ProviderExecutionError(
                    category=ProviderFailureCategory.REQUEST_DEADLINE_EXHAUSTED,
                    message=(
                        "The caller's max_latency_ms budget is exhausted; no further "
                        "provider attempt may start."
                    ),
                )
            # An attempt may wait only for what remains of the budget.
            timeout_seconds = min(timeout_seconds, remaining_seconds)
        if cost_ceiling_usd is not None:
            # Pre-attempt cost admission (issue #290): the remaining ceiling
            # must support this attempt at its conservative bound under THIS
            # candidate's rate card. Consumption is the durable attempt
            # debits, so retries and fallback candidates share one budget.
            projected = price_attempt(
                input_tokens=None,
                output_tokens=None,
                billable_risk=True,
                posture="conservative",
                fallback_input_estimate=input_estimate,
                max_output_tokens=payload_max_output,
                model_revision=model_revision,
            )
            if projected is None:
                # A hard ceiling the platform cannot price fails closed: an
                # unverifiable guarantee must not silently pass.
                raise ProviderExecutionError(
                    category=ProviderFailureCategory.REQUEST_COST_EXHAUSTED,
                    message=(
                        "The caller declared max_estimated_cost_usd, but no effective "
                        "rate card prices this candidate; the hard cost ceiling "
                        "cannot be verified and fails closed."
                    ),
                )
            spent = spent_for_execution(debit_execution_id)
            if round(spent + projected.amount_usd, 8) > cost_ceiling_usd:
                raise ProviderExecutionError(
                    category=ProviderFailureCategory.REQUEST_COST_EXHAUSTED,
                    message=(
                        "The caller's max_estimated_cost_usd budget cannot support "
                        "the next attempt at its conservative bound; no further "
                        "attempt may start on this candidate."
                    ),
                )
        # Atomic hard-budget admission (issue #300): reserve this attempt's
        # governed maximum against the global budget row BEFORE calling the
        # provider. The input bound is the request body's byte count - a
        # provable ceiling (a byte-level token is at least one byte), unlike
        # the request ceiling's documented ~4-bytes/token estimate - plus
        # the provider-enforced output cap. One store transaction makes the
        # check-and-reserve safe across replicas; settlement adjusts to the
        # evidenced amount at the attempt boundary. Unpriceable candidates
        # (no rate card) reserve nothing and never owe anything.
        reservation = price_attempt(
            input_tokens=None,
            output_tokens=None,
            billable_risk=True,
            posture="conservative",
            fallback_input_estimate=len(body),
            max_output_tokens=payload_max_output,
            model_revision=model_revision,
        )
        # An enforced hard budget that cannot price this candidate fails
        # closed (issue #329): an unpriceable attempt must not slip past the
        # limit by reserving nothing.
        require_priceable_admission(reservation)
        if reservation is not None:
            admission = reserve_attempt_spend(
                execution_id=debit_execution_id,
                candidate_entry_id=candidate_entry_id,
                provider_id=serving_provider_id,
                model_revision=model_revision,
                attempt_index=attempt_index,
                reservation=reservation,
                candidate_id_v2=candidate_id_v2,
            )
            if admission == "REFUSED":
                raise ProviderExecutionError(
                    category=ProviderFailureCategory.BUDGET_EXCEEDED,
                    message=(
                        "The live-provider hard budget cannot support this attempt's "
                        "governed maximum cost; admission is refused before the "
                        "provider is called."
                    ),
                )
        provider_request = urllib_request.Request(
            endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        attempt_started = _monotonic()
        try:
            with (
                provider_attempt_span(
                    provider_id=serving_provider_id,
                    model_id=model_identity if isinstance(model_identity, str) else None,
                    attempt=attempt_index,
                ) as attempt_span,
                urllib_request.urlopen(provider_request, timeout=timeout_seconds) as response,
            ):
                record_provider_span_outcome(attempt_span, outcome="success")
                response_payload = cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
                response_payload["_lotus_retry_count"] = attempt_index
                response_payload["_lotus_failed_attempts"] = failed_attempts
                usage = response_payload.get("usage")
                usage_fields = usage if isinstance(usage, dict) else {}
                # The served attempt debits at its own boundary too: spend is
                # real before any response-layer settlement can run.
                _debit_boundary(
                    attempt_index=attempt_index,
                    input_tokens=as_int(usage_fields.get("input_tokens")),
                    output_tokens=as_int(usage_fields.get("output_tokens")),
                    billable_risk=True,
                )
                attempt_latency_ms = _attempt_latency_ms(attempt_started)
                record_provider_attempt(
                    provider_id=serving_provider_id,
                    model_id=model_identity if isinstance(model_identity, str) else None,
                    outcome="success",
                    latency_seconds=attempt_latency_ms / 1000.0,
                )
                log_event(
                    _logger,
                    "provider_attempt",
                    provider_id=serving_provider_id,
                    model_id=model_identity,
                    attempt=attempt_index,
                    attempt_limit=bounded_retry_limit,
                    outcome="success",
                    latency_ms=attempt_latency_ms,
                    input_tokens=usage_fields.get("input_tokens"),
                    output_tokens=usage_fields.get("output_tokens"),
                )
                return response_payload
        except error.HTTPError as exc:
            error_payload = load_error_payload(exc)
            category = failure_category_for_http_status(exc.code)
            retryable = is_retryable_provider_failure(category=category, http_status_code=exc.code)
            retry_decision = plan_retry(
                backoff_plan, retry_index=attempt_index + 1, deadline_at=deadline_at
            )
            will_retry = (
                retryable and attempt_index < bounded_retry_limit and retry_decision.permitted
            )
            attempt_latency_ms = _attempt_latency_ms(attempt_started)
            record_provider_attempt(
                provider_id=serving_provider_id,
                model_id=model_identity if isinstance(model_identity, str) else None,
                outcome="retry" if will_retry else "failed",
                latency_seconds=attempt_latency_ms / 1000.0,
            )
            log_event(
                _logger,
                "provider_attempt",
                provider_id=serving_provider_id,
                model_id=model_identity,
                attempt=attempt_index,
                attempt_limit=bounded_retry_limit,
                outcome="retry" if will_retry else "failed",
                failure_class=category.value,
                http_status=exc.code,
                latency_ms=attempt_latency_ms,
            )
            # 5xx may follow completed generation; 4xx (incl. 429) refuses
            # before generation and carries no billable risk. The debit
            # happens HERE, terminal or not: an execution whose every
            # attempt fails has still moved the envelope (issue #289).
            evidence = _failed_attempt_evidence(error_payload, billable_risk=exc.code >= 500)
            error_input_tokens = as_int(evidence.get("input_tokens"))
            if error_input_tokens is not None:
                # Provider-reported input on a failed attempt is hard
                # evidence for later conservative estimates of the same body.
                input_estimate = error_input_tokens
            debit = _debit_boundary(
                attempt_index=attempt_index,
                input_tokens=error_input_tokens,
                output_tokens=as_int(evidence.get("output_tokens")),
                billable_risk=exc.code >= 500,
            )
            if will_retry:
                failed_attempts.append(_with_debit(evidence, debit))
                wait_for_retry(retry_decision)
                continue
            deadline_stop = _governed_deadline_stop(
                execution_deadline_at=execution_deadline_at,
                retryable=retryable,
                attempt_index=attempt_index,
                retry_limit=bounded_retry_limit,
                delay_seconds=retry_decision.delay_seconds,
            )
            if deadline_stop is not None:
                raise deadline_stop from exc
            raise ProviderExecutionError(
                category=category,
                message=safe_provider_error_message(
                    category=category,
                    serving_provider_id=serving_provider_id,
                ),
            ) from exc
        except TimeoutError as exc:
            retry_decision = plan_retry(
                backoff_plan, retry_index=attempt_index + 1, deadline_at=deadline_at
            )
            will_retry = attempt_index < bounded_retry_limit and retry_decision.permitted
            attempt_latency_ms = _attempt_latency_ms(attempt_started)
            record_provider_attempt(
                provider_id=serving_provider_id,
                model_id=model_identity if isinstance(model_identity, str) else None,
                outcome="retry" if will_retry else "failed",
                latency_seconds=attempt_latency_ms / 1000.0,
            )
            log_event(
                _logger,
                "provider_attempt",
                provider_id=serving_provider_id,
                model_id=model_identity,
                attempt=attempt_index,
                attempt_limit=bounded_retry_limit,
                outcome="retry" if will_retry else "failed",
                failure_class=ProviderFailureCategory.PROVIDER_TIMEOUT.value,
                latency_ms=attempt_latency_ms,
            )
            # A timeout after acceptance may still have generated and billed
            # provider-side - debited at the boundary, terminal or not.
            debit = _debit_boundary(
                attempt_index=attempt_index,
                input_tokens=None,
                output_tokens=None,
                billable_risk=True,
            )
            if will_retry:
                failed_attempts.append(
                    _with_debit(_failed_attempt_evidence({}, billable_risk=True), debit)
                )
                wait_for_retry(retry_decision)
                continue
            deadline_stop = _governed_deadline_stop(
                execution_deadline_at=execution_deadline_at,
                retryable=True,
                attempt_index=attempt_index,
                retry_limit=bounded_retry_limit,
                delay_seconds=retry_decision.delay_seconds,
            )
            if deadline_stop is not None:
                raise deadline_stop from exc
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                message=safe_provider_error_message(
                    category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                    serving_provider_id=serving_provider_id,
                ),
            ) from exc
        except error.URLError as exc:
            retry_decision = plan_retry(
                backoff_plan, retry_index=attempt_index + 1, deadline_at=deadline_at
            )
            will_retry = attempt_index < bounded_retry_limit and retry_decision.permitted
            attempt_latency_ms = _attempt_latency_ms(attempt_started)
            record_provider_attempt(
                provider_id=serving_provider_id,
                model_id=model_identity if isinstance(model_identity, str) else None,
                outcome="retry" if will_retry else "failed",
                latency_seconds=attempt_latency_ms / 1000.0,
            )
            log_event(
                _logger,
                "provider_attempt",
                provider_id=serving_provider_id,
                model_id=model_identity,
                attempt=attempt_index,
                attempt_limit=bounded_retry_limit,
                outcome="retry" if will_retry else "failed",
                failure_class=ProviderFailureCategory.PROVIDER_TIMEOUT.value,
                latency_ms=attempt_latency_ms,
            )
            # Connection-level failure: the request did not reach a
            # generating provider, so no billable risk - the reservation is
            # released to zero at the same boundary (issue #300).
            _debit_boundary(
                attempt_index=attempt_index,
                input_tokens=None,
                output_tokens=None,
                billable_risk=False,
            )
            if will_retry:
                failed_attempts.append(_failed_attempt_evidence({}, billable_risk=False))
                wait_for_retry(retry_decision)
                continue
            deadline_stop = _governed_deadline_stop(
                execution_deadline_at=execution_deadline_at,
                retryable=True,
                attempt_index=attempt_index,
                retry_limit=bounded_retry_limit,
                delay_seconds=retry_decision.delay_seconds,
            )
            if deadline_stop is not None:
                raise deadline_stop from exc
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                message=safe_provider_error_message(
                    category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                    serving_provider_id=serving_provider_id,
                ),
            ) from exc
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        message=safe_provider_error_message(
            category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
            serving_provider_id=serving_provider_id,
        ),
    )


_logger = logging.getLogger("app.provider")


def is_advisor_brief_payload(payload: dict[str, Any]) -> bool:
    return {"portfolio", "period", "performance", "supportability"}.issubset(payload.keys())


def build_structured_output(
    *,
    descriptor: ProviderAdapterDescriptor,
    request: ProviderExecutionRequest,
    response_payload: dict[str, Any],
    output_message: str,
    configured_model_id: str | None = None,
    provider_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    structured_output: dict[str, Any] = {
        "provider_id": provider_id or descriptor.provider_id,
        "provider_mode": descriptor.runtime_mode.value,
        "adapter_kind": descriptor.adapter_kind.value,
        "model_id": as_str(response_payload.get("model")) or configured_model_id,
        "provider_request_id": as_str(response_payload.get("id")),
        "output_label": request.output_label,
        "safety_mode": request.safety_mode,
        "redaction_posture": request.redaction_posture,
        "source_refs": request.source_refs,
        "retry_count": extract_retry_count(response_payload),
    }
    input_tokens, output_tokens, total_tokens = extract_usage(response_payload)
    structured_cost = estimate_live_text_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_revision=configured_model_id,
    )
    structured_billing = project_attempt_billing(
        final_cost=structured_cost,
        failed_debits=extract_failed_attempt_debits(response_payload),
        had_failed_attempts=bool(extract_failed_attempts(response_payload)),
    )
    structured_output.update(
        {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            # The attempt-summed figure (issue #232) - the same number the
            # budget envelope records. The composition detail (basis, counts)
            # lives on the response and audit record: the echo's SHAPE is
            # pinned by the captured pack output contracts, so new keys here
            # would fail output validation for every family.
            "estimated_cost_usd": structured_billing.estimated_cost_usd,
            "rate_card_ref": structured_cost.rate_card_ref,
            "cost_posture": structured_cost.cost_posture,
        }
    )
    if is_advisor_brief_payload(request.context_payload):
        parsed, salvaged = parse_json_object_with_posture(output_message)
        if salvaged:
            # The validator decides what salvage means per profile (issue
            # #156): promoted rejects, local marks UNVALIDATED_LOCAL_ONLY.
            structured_output["strict_json_salvaged"] = True
        quality_result = normalize_advisor_brief_output(
            parsed_output=parsed,
            output_message=output_message,
            context_payload=request.context_payload,
            source_refs=request.source_refs,
        )
        structured_output.update(quality_result.structured_output)
        return quality_result.message, structured_output

    if is_idea_explanation_payload(request.context_payload):
        parsed, salvaged = parse_json_object_with_posture(output_message)
        idea_result = normalize_idea_explanation_output(
            parsed_output=parsed,
            salvaged=salvaged,
            output_message=output_message,
            context_payload=request.context_payload,
        )
        if idea_result is not None:
            if idea_result.refusal_reason is not None:
                # Never manufacture (issue #330): the model-authored section
                # is withheld and the registered pack contract rejects the
                # output whole; the bounded reason is operator evidence.
                log_event(
                    _logger,
                    "idea_explanation_output_refused",
                    refusal_reason=idea_result.refusal_reason,
                )
            structured_output.update(idea_result.structured_output)
            return idea_result.message, structured_output

    return output_message, structured_output


def _governed_deadline_stop(
    *,
    execution_deadline_at: float | None,
    retryable: bool,
    attempt_index: int,
    retry_limit: int,
    delay_seconds: float,
) -> ProviderExecutionError | None:
    """The error to raise when the governed budget - not the retry plan - is
    what stopped a retry that was otherwise permitted.

    Distinguishability is the requirement (issue #244): a candidate that
    stopped because the caller's max_latency_ms ran out must not report a
    provider condition the provider never caused.
    """

    if execution_deadline_at is None:
        return None
    if not retryable or attempt_index >= retry_limit:
        return None
    if _monotonic() + delay_seconds <= execution_deadline_at:
        return None
    return ProviderExecutionError(
        category=ProviderFailureCategory.REQUEST_DEADLINE_EXHAUSTED,
        message=(
            "The caller's max_latency_ms budget cannot support another retry; the "
            "provider attempt sequence stopped at the governed deadline."
        ),
    )


def _monotonic() -> float:
    """Seam for the governed-deadline clock; tests replace it."""

    return time.perf_counter()


def _attempt_latency_ms(started: float) -> float:
    return round((_monotonic() - started) * 1000.0, 3)


def load_error_payload(exc: error.HTTPError) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(exc.read().decode("utf-8")))
    except json.JSONDecodeError:
        return {}


def failure_category_for_http_status(http_status_code: int) -> ProviderFailureCategory:
    if http_status_code == 429:
        return ProviderFailureCategory.PROVIDER_RATE_LIMITED
    return ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR


def is_retryable_provider_failure(
    *, category: ProviderFailureCategory, http_status_code: int | None = None
) -> bool:
    if category in {
        ProviderFailureCategory.PROVIDER_TIMEOUT,
        ProviderFailureCategory.PROVIDER_RATE_LIMITED,
    }:
        return True
    return category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR and http_status_code in {
        408,
        500,
        502,
        503,
        504,
    }


def safe_provider_error_message(
    *, category: ProviderFailureCategory, serving_provider_id: str
) -> str:
    if category == ProviderFailureCategory.PROVIDER_RATE_LIMITED:
        return f"{serving_provider_id} rate limit exceeded."
    if category == ProviderFailureCategory.PROVIDER_TIMEOUT:
        return f"{serving_provider_id} request did not complete within the configured timeout."
    return f"{serving_provider_id} request failed at the upstream provider boundary."


def extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    output = payload.get("output")
    if isinstance(output, list):
        fragments: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    fragments.append(text.strip())
        if fragments:
            return "\n".join(fragments)
    raise ProviderExecutionError(
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        message="OpenAI-compatible provider response did not include output text.",
    )


def extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return (None, None, None)
    return (
        as_int(usage.get("input_tokens")),
        as_int(usage.get("output_tokens")),
        as_int(usage.get("total_tokens")),
    )


def extract_retry_count(payload: dict[str, Any]) -> int:
    return as_int(payload.get("_lotus_retry_count")) or 0


def _failed_attempt_evidence(
    error_payload: dict[str, Any], *, billable_risk: bool
) -> dict[str, object]:
    """What one failed attempt is known to have used (issue #232).

    An OpenAI-compatible error body rarely carries usage, but when it does
    that is actual billing evidence and beats any estimate.
    """

    usage = error_payload.get("usage")
    usage_fields = usage if isinstance(usage, dict) else {}
    return {
        "billable_risk": billable_risk,
        "input_tokens": as_int(usage_fields.get("input_tokens")),
        "output_tokens": as_int(usage_fields.get("output_tokens")),
    }


def _with_debit(evidence: dict[str, object], debit: AttemptDebit | None) -> dict[str, object]:
    """Stamp what the boundary durably recorded onto the attempt evidence, so
    the response projection restates the recorded numbers rather than
    re-estimating them (issue #289)."""

    if debit is not None:
        evidence["debit_usd"] = debit.amount_usd
        evidence["debit_basis"] = debit.basis
        evidence["debit_input_tokens"] = debit.input_tokens
        evidence["debit_output_tokens"] = debit.output_tokens
        evidence["debit_rate_card_ref"] = debit.rate_card_ref
    return evidence


def extract_failed_attempt_debits(payload: dict[str, Any]) -> list[AttemptDebit]:
    debits: list[AttemptDebit] = []
    for attempt in extract_failed_attempts(payload):
        amount = attempt.get("debit_usd")
        basis = attempt.get("debit_basis")
        rate_card_ref = attempt.get("debit_rate_card_ref")
        if (
            isinstance(amount, (int, float))
            and not isinstance(amount, bool)
            and basis in ("ACTUAL_USAGE", "CONSERVATIVE_ESTIMATE")
            and isinstance(rate_card_ref, str)
        ):
            input_tokens = attempt.get("debit_input_tokens")
            output_tokens = attempt.get("debit_output_tokens")
            debits.append(
                AttemptDebit(
                    amount_usd=float(amount),  # monetary-float-ok: restating the recorded debit
                    basis=basis,
                    input_tokens=input_tokens if isinstance(input_tokens, int) else None,
                    output_tokens=output_tokens if isinstance(output_tokens, int) else None,
                    rate_card_ref=rate_card_ref,
                )
            )
    return debits


def extract_failed_attempts(payload: dict[str, Any]) -> list[dict[str, object]]:
    attempts = payload.get("_lotus_failed_attempts")
    return (
        [attempt for attempt in attempts if isinstance(attempt, dict)]
        if isinstance(attempts, list)
        else []
    )


OPENAI_MANAGED_TEXT_DESCRIPTOR = ProviderAdapterDescriptor(
    provider_id="text.openai",
    display_name="OpenAI Managed Text Provider",
    capability=ProviderCapability.TEXT_GENERATION,
    adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
    runtime_mode=ProviderExecutionMode.OPENAI,
    enabled_for_execution=False,
    failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
    source_reference="docs/rfcs/RFC-0003-controlled-live-provider-backbone.md",
    notes=(
        "Allowlisted OpenAI-backed live text-generation path. Runtime activation remains "
        "disabled by default until rollout, allowlist, and governance gates are satisfied."
    ),
)


LOCAL_OPENAI_COMPATIBLE_TEXT_DESCRIPTOR = ProviderAdapterDescriptor(
    provider_id="text.local",
    display_name="Local OpenAI-Compatible Text Provider",
    capability=ProviderCapability.TEXT_GENERATION,
    adapter_kind=ProviderAdapterKind.OPENAI_COMPATIBLE_LOCAL,
    runtime_mode=ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE,
    enabled_for_execution=False,
    failure_category_on_use=ProviderFailureCategory.LIVE_EXECUTION_NOT_ENABLED,
    source_reference="docs/rfcs/RFC-0027-local-and-remote-openai-compatible-provider-routing.md",
    notes=(
        "Governed local or self-hosted OpenAI-compatible text-generation path for private "
        "deployment, developer-local validation, and billing-controlled execution."
    ),
)
