"""Attempt-level durable billing (issue #289, superseding #232's settlement).

Every potentially billable provider attempt debits Lotus spend exactly once
at its own boundary - durably, idempotently, and regardless of whether the
execution later succeeds, fails completely, falls back, or the process dies.
The response, when one exists, merely projects the recorded evidence.
"""

from email.message import Message
from io import BytesIO
from urllib import error

from pytest import MonkeyPatch, raises

from app.config import settings
from app.contracts.model_catalogue import derive_candidate_identity_v2
from app.contracts.providers import ProviderExecutionResponse
from app.providers.base import ProviderExecutionError
from app.services.provider_operations_store import get_provider_operations_store
from app.services.provider_usage_accounting import (
    AttemptDebit,
    UsageCostEstimate,
    price_attempt,
    project_attempt_billing,
)


def _seed_cost_scalars() -> None:
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03


def test_price_attempt_follows_the_evidence_order() -> None:
    _seed_cost_scalars()

    actual = price_attempt(
        input_tokens=200,
        output_tokens=100,
        billable_risk=True,
        posture="conservative",
        fallback_input_estimate=999,
        max_output_tokens=512,
        model_revision="gpt-5.4",
    )
    assert actual is not None
    assert actual.basis == "ACTUAL_USAGE"
    assert actual.amount_usd == 0.005
    assert actual.rate_card_ref

    conservative = price_attempt(
        input_tokens=None,
        output_tokens=None,
        billable_risk=True,
        posture="conservative",
        fallback_input_estimate=200,
        max_output_tokens=512,
        model_revision="gpt-5.4",
    )
    assert conservative is not None
    assert conservative.basis == "CONSERVATIVE_ESTIMATE"
    assert conservative.amount_usd == 0.01736
    assert conservative.input_tokens == 200
    assert conservative.output_tokens == 512

    # Non-billable risk, actual_only posture, or a missing rate card never
    # price - no debit is the explicit outcome, not a silent zero.
    assert (
        price_attempt(
            input_tokens=None,
            output_tokens=None,
            billable_risk=False,
            posture="conservative",
            fallback_input_estimate=200,
            max_output_tokens=512,
            model_revision="gpt-5.4",
        )
        is None
    )
    assert (
        price_attempt(
            input_tokens=None,
            output_tokens=None,
            billable_risk=True,
            posture="actual_only",
            fallback_input_estimate=200,
            max_output_tokens=512,
            model_revision="gpt-5.4",
        )
        is None
    )


def test_projection_restates_recorded_debits() -> None:
    final = UsageCostEstimate(estimated_cost_usd=0.0035, rate_card_ref="default-live-text")
    conservative = AttemptDebit(
        amount_usd=0.01736,
        basis="CONSERVATIVE_ESTIMATE",
        input_tokens=200,
        output_tokens=512,
        rate_card_ref="default-live-text",
    )
    actual = AttemptDebit(
        amount_usd=0.005,
        basis="ACTUAL_USAGE",
        input_tokens=200,
        output_tokens=100,
        rate_card_ref="default-live-text",
    )

    single = project_attempt_billing(final_cost=final, failed_debits=[], had_failed_attempts=False)
    assert single.estimated_cost_usd == 0.0035
    assert single.failed_attempt_cost_usd is None
    assert single.failed_attempt_cost_basis is None
    assert single.billed_attempt_count == 1

    unbilled = project_attempt_billing(final_cost=final, failed_debits=[], had_failed_attempts=True)
    assert unbilled.failed_attempt_cost_basis == "NONE"
    assert unbilled.billed_attempt_count == 1

    mixed = project_attempt_billing(
        final_cost=final, failed_debits=[conservative, actual], had_failed_attempts=True
    )
    assert mixed.failed_attempt_cost_basis == "MIXED"
    assert mixed.failed_attempt_cost_usd == 0.02236
    assert mixed.estimated_cost_usd == 0.02586
    assert mixed.billed_attempt_count == 3


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


_SUCCESS_BODY = (
    b'{"id": "resp_billing", "model": "gpt-5.4", "output_text": "OK",'
    b' "usage": {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250}}'
)


def _quiet_backoff(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.provider_retry_backoff._sleep", lambda delay: None)
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)


def _http_error(code: int) -> error.HTTPError:
    return error.HTTPError(
        url="http://localhost/v1/responses",
        code=code,
        msg="failure",
        hdrs=Message(),
        fp=BytesIO(b"{}"),
    )


_CANONICAL_GPT54 = derive_candidate_identity_v2(
    provider_id="text.local",
    model_family="gpt-5.4",
    model_revision="gpt-5.4",
    deployment=None,
)


def _debit_key(execution_id: str, attempt_index: int) -> str:
    """The canonical-segment debit identity minted by the transport (issue #326)."""

    return f"adbt2:{execution_id}:{_CANONICAL_GPT54}:{attempt_index}"


def _run_transport(*, retry_limit: int, execution_id: str) -> "ProviderExecutionResponse":
    from app.providers.local_openai_compatible_text_provider import (
        LocalOpenAICompatibleTextProvider,
    )
    from app.providers.openai_compatible_text_transport import (
        execute_openai_compatible_text_request,
    )
    from tests.unit.test_provider_gateway import _request

    return execute_openai_compatible_text_request(
        descriptor=LocalOpenAICompatibleTextProvider().descriptor,
        request=_request(retry_limit=retry_limit, execution_id=execution_id),
        api_base="http://localhost:1234/v1",
        api_key=None,
        require_api_key=False,
        model_id="gpt-5.4",
        model_version=None,
    )


def test_served_execution_debits_each_attempt_and_projects_them(
    monkeypatch: MonkeyPatch,
) -> None:
    """Fails once with a 5xx, succeeds on retry: BOTH attempts are durable
    debit rows and the budget envelope moved at each boundary. The 5xx
    attempt revealed no usage, so its row HOLDS the reserved maximum as
    UNRESOLVED_MAX exposure (issue #329) - the response reports the estimate,
    but the estimate releases nothing."""

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)
    attempts = {"count": 0}

    def _urlopen(request: object, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _http_error(503)
        return _Response(_SUCCESS_BODY)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = _run_transport(retry_limit=1, execution_id="exec-served")

    rows = {row.debit_id: row for row in get_provider_operations_store().list_attempt_debits()}
    failed_row = rows[_debit_key("exec-served", 0)]
    served_row = rows[_debit_key("exec-served", 1)]
    # The full serving identity rides the durable evidence (issue #299).
    assert served_row.candidate_entry_id == "text.local:gpt-5.4"
    assert served_row.model_revision == "gpt-5.4"
    assert served_row.attempt_index == 1
    assert served_row.provider_id == "text.local"
    assert failed_row.basis == "UNRESOLVED_MAX"
    assert failed_row.output_tokens == 512
    assert served_row.basis == "ACTUAL_USAGE"
    assert served_row.amount_usd == 0.0035

    # The response reports the ESTIMATE for the failed attempt - honest
    # reporting posture - while the durable row holds the larger reserved
    # maximum: the three-way distinction between estimate, unresolved
    # reservation, and evidenced charge is visible in one execution.
    assert response.failed_attempt_cost_usd is not None
    assert failed_row.amount_usd > response.failed_attempt_cost_usd
    assert response.estimated_cost_usd == round(
        response.failed_attempt_cost_usd + served_row.amount_usd, 8
    )
    assert response.failed_attempt_cost_basis == "CONSERVATIVE_ESTIMATE"
    assert response.billed_attempt_count == 2
    assert response.structured_output["estimated_cost_usd"] == response.estimated_cost_usd

    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    # The counter keeps the unresolved maximum, not the estimate: unknown
    # usage never releases hard admission capacity at the boundary.
    assert budget.current_spend_usd == round(failed_row.amount_usd + served_row.amount_usd, 8)
    assert budget.current_spend_usd > response.estimated_cost_usd


def test_terminal_all_fail_execution_still_debits_every_billable_attempt(
    monkeypatch: MonkeyPatch,
) -> None:
    """The steering's P1 case: no success ever exists, yet both billable-risk
    attempts moved the envelope at their boundaries - and with no usage ever
    revealed, both rows hold their reserved maxima as UNRESOLVED_MAX
    exposure (issue #329) rather than releasing to the heuristic estimate."""

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)

    def _urlopen(request: object, timeout: float) -> _Response:
        raise _http_error(503)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    with raises(ProviderExecutionError):
        _run_transport(retry_limit=1, execution_id="exec-allfail")

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt2:exec-allfail:")
    ]
    assert {row.debit_id for row in rows} == {
        _debit_key("exec-allfail", 0),
        _debit_key("exec-allfail", 1),
    }
    assert all(row.basis == "UNRESOLVED_MAX" for row in rows)
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == round(sum(row.amount_usd for row in rows), 8)


def test_rate_limited_and_pre_connect_failures_never_debit(
    monkeypatch: MonkeyPatch,
) -> None:
    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)
    attempts = {"count": 0}

    def _urlopen(request: object, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _http_error(429)
        if attempts["count"] == 2:
            raise error.URLError("connection refused")
        return _Response(_SUCCESS_BODY)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = _run_transport(retry_limit=2, execution_id="exec-unbillable")

    rows = {
        row.debit_id: row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt2:exec-unbillable:")
    }
    # Only the served attempt carries spend: 429 refused before generation
    # and the connection-level failure never reached a generating provider.
    # Their pre-attempt reservations (issue #300) settle to zero-amount
    # RELEASED rows - admitted-then-released is durable evidence, not spend.
    assert rows[_debit_key("exec-unbillable", 0)].basis == "RELEASED"
    assert rows[_debit_key("exec-unbillable", 0)].amount_usd == 0.0
    assert rows[_debit_key("exec-unbillable", 1)].basis == "RELEASED"
    assert rows[_debit_key("exec-unbillable", 1)].amount_usd == 0.0
    assert rows[_debit_key("exec-unbillable", 2)].basis == "ACTUAL_USAGE"
    assert response.estimated_cost_usd == 0.0035
    assert response.failed_attempt_cost_basis == "NONE"
    assert response.billed_attempt_count == 1
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == 0.0035


def test_candidates_sharing_an_execution_debit_cumulatively(
    monkeypatch: MonkeyPatch,
) -> None:
    """Fallback semantics (issue #289): candidates share one execution
    identity, each attempt keys its own debit, and spend accumulates - it is
    never reset between candidates."""

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)
    from app.providers.openai_compatible_text_transport import (
        post_openai_compatible_response,
    )

    def _urlopen(request: object, timeout: float) -> _Response:
        raise _http_error(503)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    for provider_id in ("text.primary", "text.alternate"):
        with raises(ProviderExecutionError):
            post_openai_compatible_response(
                api_base="http://localhost:1234/v1",
                api_key=None,
                payload={"model": "gpt-5.4", "max_output_tokens": 512},
                timeout_seconds=1.0,
                serving_provider_id=provider_id,
                require_api_key=False,
                retry_limit=0,
                execution_id="exec-fallback",
                model_revision="gpt-5.4",
            )

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-fallback:")
    ]
    assert {row.debit_id for row in rows} == {
        "adbt:exec-fallback:text.primary:gpt-5.4:0",
        "adbt:exec-fallback:text.alternate:gpt-5.4:0",
    }
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == round(sum(row.amount_usd for row in rows), 8)


def _post_candidate(
    *,
    provider_id: str,
    model_revision: str,
    execution_id: str,
    retry_limit: int = 0,
) -> dict[str, object]:
    from app.providers.openai_compatible_text_transport import (
        post_openai_compatible_response,
    )

    return post_openai_compatible_response(
        api_base="http://localhost:1234/v1",
        api_key=None,
        payload={"model": "gpt-5.4", "max_output_tokens": 512},
        timeout_seconds=1.0,
        serving_provider_id=provider_id,
        require_api_key=False,
        retry_limit=retry_limit,
        execution_id=execution_id,
        model_revision=model_revision,
    )


def test_same_provider_model_candidates_debit_distinctly(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #299: two model candidates at the SAME provider, attempt 0 each,
    are two debit records - a provider-keyed identity would have swallowed
    the second as a duplicate and understated spend. Both records reach the
    execution's consumed spend and the global budget envelope."""

    from app.services.provider_budget_policy import spent_for_execution

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)

    def _urlopen(request: object, timeout: float) -> _Response:
        raise _http_error(503)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    for revision in ("model-a", "model-b"):
        with raises(ProviderExecutionError):
            _post_candidate(
                provider_id="text.shared",
                model_revision=revision,
                execution_id="exec-shared-provider",
            )

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-shared-provider:")
    ]
    assert {row.debit_id for row in rows} == {
        "adbt:exec-shared-provider:text.shared:model-a:0",
        "adbt:exec-shared-provider:text.shared:model-b:0",
    }
    assert {row.candidate_entry_id for row in rows} == {
        "text.shared:model-a",
        "text.shared:model-b",
    }
    assert all(row.provider_id == "text.shared" for row in rows)
    total = round(sum(row.amount_usd for row in rows), 8)
    assert total > 0
    assert spent_for_execution("exec-shared-provider") == total
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == total


def test_a_retry_attempt_stays_distinct_from_a_fallback_attempt(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #299: candidate A's retry (attempt 1) and same-provider
    candidate B's first attempt (attempt 0) are different debits - attempt
    indices restart per candidate, so only the candidate segment keeps them
    apart."""

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)

    def _urlopen(request: object, timeout: float) -> _Response:
        raise _http_error(503)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    with raises(ProviderExecutionError):
        _post_candidate(
            provider_id="text.shared",
            model_revision="model-a",
            execution_id="exec-retry-vs-fallback",
            retry_limit=1,
        )
    with raises(ProviderExecutionError):
        _post_candidate(
            provider_id="text.shared",
            model_revision="model-b",
            execution_id="exec-retry-vs-fallback",
        )

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-retry-vs-fallback:")
    ]
    assert {row.debit_id for row in rows} == {
        "adbt:exec-retry-vs-fallback:text.shared:model-a:0",
        "adbt:exec-retry-vs-fallback:text.shared:model-a:1",
        "adbt:exec-retry-vs-fallback:text.shared:model-b:0",
    }


def test_three_same_provider_fallback_candidates_accumulate(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #299 / the wider-universe north star: three candidates from ONE
    provider all debit, spend accumulates across the shared execution, and
    the durable rows are the number the envelope moved by."""

    from app.services.provider_budget_policy import spent_for_execution

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)

    def _urlopen(request: object, timeout: float) -> _Response:
        raise _http_error(503)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    for revision in ("model-a", "model-b", "model-c"):
        with raises(ProviderExecutionError):
            _post_candidate(
                provider_id="text.shared",
                model_revision=revision,
                execution_id="exec-three-candidates",
            )

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-three-candidates:")
    ]
    assert len(rows) == 3
    total = round(sum(row.amount_usd for row in rows), 8)
    assert spent_for_execution("exec-three-candidates") == total
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == total


def test_hard_budget_refuses_admission_before_the_provider_is_called(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #300: "hard" means enforceable BEFORE the money moves - an
    attempt whose governed maximum (input bounded by request-body bytes,
    output by the enforced cap) cannot fit the hard budget is refused with
    nothing written and the provider never called."""

    _seed_cost_scalars()
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 0.001
    calls = {"count": 0}

    def _urlopen(request: object, timeout: float) -> _Response:
        calls["count"] += 1
        return _Response(_SUCCESS_BODY)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    with raises(ProviderExecutionError) as exc_info:
        _post_candidate(
            provider_id="text.shared",
            model_revision="model-a",
            execution_id="exec-hard-budget",
        )

    assert exc_info.value.category.value == "BUDGET_EXCEEDED"
    assert calls["count"] == 0
    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-hard-budget:")
    ]
    assert rows == []
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is None or budget.current_spend_usd == 0.0


def test_the_reservation_bound_survives_input_larger_than_the_estimate(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #300/#301 boundary: provider-reported input tokens EXCEED the
    request ceiling's ~4-bytes/token heuristic, yet stay within the
    reservation's provable byte-count bound - the hard budget's governed
    maximum was genuinely conservative, and the settled debit records the
    larger actual usage."""

    _seed_cost_scalars()
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 5.0

    body_probe: dict[str, int] = {}

    def _urlopen(request: object, timeout: float) -> _Response:
        data = getattr(request, "data", b"") or b""
        body_probe["bytes"] = len(data)
        # Report input usage above bytes//4 but below the byte count.
        oversized_input = max(len(data) // 2, 1)
        return _Response(
            (
                '{"id": "resp_billing", "model": "gpt-5.4", "output_text": "OK",'
                f' "usage": {{"input_tokens": {oversized_input}, "output_tokens": 10,'
                f' "total_tokens": {oversized_input + 10}}}}}'
            ).encode("utf-8")
        )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    _post_candidate(
        provider_id="text.shared",
        model_revision="model-a",
        execution_id="exec-oversized-input",
    )

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-oversized-input:")
    ]
    assert len(rows) == 1
    settled = rows[0]
    assert settled.basis == "ACTUAL_USAGE"
    assert settled.input_tokens is not None
    # The actual usage beat the heuristic yet stayed under the provable bound.
    assert settled.input_tokens > body_probe["bytes"] // 4
    assert settled.input_tokens <= body_probe["bytes"]


def test_gateway_mints_one_execution_identity_per_execution(
    monkeypatch: MonkeyPatch,
) -> None:
    """The gateway stamps execution_id once, at the top of the execution,
    before candidate dispatch - retries and fallback candidates then share
    it, and a fresh execution gets a fresh identity."""

    from fastapi import HTTPException

    from app.contracts.providers import ProviderExecutionRequest, ProviderFailureCategory
    from app.services import provider_gateway
    from app.services.provider_execution_config import ProviderExecutionConfig
    from tests.unit.test_provider_gateway import _request

    settings.provider_mode = "stub"
    captured: list[str | None] = []

    class _Adapter:
        def execute(
            self, request: ProviderExecutionRequest, *, config: ProviderExecutionConfig
        ) -> object:
            captured.append(request.execution_id)
            raise ProviderExecutionError(
                category=ProviderFailureCategory.UNSUPPORTED_MODE,
                message="capture only",
            )

    monkeypatch.setattr(
        provider_gateway, "resolve_text_generation_adapter", lambda mode: _Adapter()
    )

    for _ in range(2):
        with raises(HTTPException):
            provider_gateway.execute_text_generation(_request())
    with raises(HTTPException):
        provider_gateway.execute_text_generation(_request(execution_id="exec-preset"))

    assert len(captured) == 3
    assert captured[0] and captured[1]
    assert captured[0] != captured[1]
    # A caller-supplied identity is preserved, never re-minted.
    assert captured[2] == "exec-preset"


def _post_with_ceiling(
    *,
    provider_id: str,
    model_revision: str,
    execution_id: str,
    ceiling: float,
    retry_limit: int = 0,
) -> dict[str, object]:
    from app.providers.openai_compatible_text_transport import (
        post_openai_compatible_response,
    )

    return post_openai_compatible_response(
        api_base="http://localhost:1234/v1",
        api_key=None,
        payload={"model": "gpt-5.4", "max_output_tokens": 512},
        timeout_seconds=1.0,
        serving_provider_id=provider_id,
        require_api_key=False,
        retry_limit=retry_limit,
        execution_id=execution_id,
        model_revision=model_revision,
        cost_ceiling_usd=ceiling,
    )


def test_cost_ceiling_refuses_the_next_attempt_before_it_starts(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #290: one execution budget - the first attempt's conservative
    debit consumes it, and the second attempt is refused pre-connect with
    the bounded category; nothing is billed for the refused attempt."""

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)
    calls = {"count": 0}

    def _urlopen(request: object, timeout: float) -> _Response:
        calls["count"] += 1
        raise _http_error(503)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    # Conservative bound per attempt with these scalars is well over 0.02:
    # the first attempt fits, the retry cannot.
    with raises(ProviderExecutionError) as exc_info:
        _post_with_ceiling(
            provider_id="text.local",
            model_revision="gpt-5.4",
            execution_id="exec-ceiling",
            ceiling=0.02,
            retry_limit=1,
        )

    assert exc_info.value.category.value == "REQUEST_COST_EXHAUSTED"
    assert calls["count"] == 1
    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-ceiling:")
    ]
    assert {row.debit_id for row in rows} == {"adbt:exec-ceiling:text.local:gpt-5.4:0"}


def test_a_cheaper_fallback_candidate_fits_the_shared_remaining_ceiling(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #290: the ceiling is shared, never reset - and the alternate's
    admission prices under the ALTERNATE's rate card, so a cheaper candidate
    fits where the primary would not."""

    from app.contracts.rate_cards import RateCard, RateCardScopeKind
    from app.services.provider_usage_accounting import save_rate_card

    _seed_cost_scalars()
    _quiet_backoff(monkeypatch)
    save_rate_card(
        RateCard(
            card_id="cheap-alternate",
            scope_kind=RateCardScopeKind.MODEL_REVISION,
            scope_target="cheap-rev",
            currency="USD",
            input_cost_per_1k_tokens=0.0001,
            output_cost_per_1k_tokens=0.0001,
            effective_from_utc=None,
            effective_to_utc=None,
            created_at="2026-08-31T00:00:00Z",
            last_updated_at="2026-08-31T00:00:00Z",
        )
    )
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: _Response(_SUCCESS_BODY))

    # The primary's conservative bound under the default card exceeds the
    # ceiling outright: refused before any connection.
    with raises(ProviderExecutionError) as exc_info:
        _post_with_ceiling(
            provider_id="text.primary",
            model_revision="gpt-5.4",
            execution_id="exec-cheap-fallback",
            ceiling=0.01,
        )
    assert exc_info.value.category.value == "REQUEST_COST_EXHAUSTED"

    payload = _post_with_ceiling(
        provider_id="text.alternate",
        model_revision="cheap-rev",
        execution_id="exec-cheap-fallback",
        ceiling=0.01,
    )
    assert payload["id"] == "resp_billing"
    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-cheap-fallback:")
    ]
    # Only the alternate billed, under its own card.
    assert {row.debit_id for row in rows} == {"adbt:exec-cheap-fallback:text.alternate:cheap-rev:0"}
    assert rows[0].rate_card_ref == "cheap-alternate"


def test_the_ceiling_bounds_the_estimate_never_actual_billing(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #301: the contract decision made explicit. Admission runs on the
    governed pre-execution estimate (~4 bytes/token); the provider then
    reports input usage FAR above the heuristic - the settled debit and the
    response project the larger ACTUAL amount, even beyond the declared
    ceiling. The ceiling bounded the estimate, exactly as documented, and no
    surface pretends actual billing was capped."""

    _seed_cost_scalars()

    def _urlopen(request: object, timeout: float) -> _Response:
        return _Response(
            b'{"id": "resp_billing", "model": "gpt-5.4", "output_text": "OK",'
            b' "usage": {"input_tokens": 200000, "output_tokens": 10,'
            b' "total_tokens": 200010}}'
        )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    payload = _post_with_ceiling(
        provider_id="text.local",
        model_revision="gpt-5.4",
        execution_id="exec-estimate-contract",
        ceiling=1.0,
    )
    assert payload["id"] == "resp_billing"

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt:exec-estimate-contract:")
    ]
    assert len(rows) == 1
    settled = rows[0]
    assert settled.basis == "ACTUAL_USAGE"
    assert settled.input_tokens == 200000
    # The actual settled amount exceeds the declared ceiling: the ceiling is
    # an estimate bound, and the durable evidence records the actual truth
    # rather than clamping to the claim.
    assert settled.amount_usd > 1.0


def test_a_declared_ceiling_on_an_unpriceable_candidate_fails_closed() -> None:
    """Issue #290: no rate card means the ceiling cannot be verified - the
    guarantee refuses rather than silently passing."""

    with raises(ProviderExecutionError) as exc_info:
        _post_with_ceiling(
            provider_id="text.local",
            model_revision="unpriced-rev",
            execution_id="exec-unpriceable",
            ceiling=5.0,
        )
    assert exc_info.value.category.value == "REQUEST_COST_EXHAUSTED"
    assert "cannot be verified" in exc_info.value.message


def test_gateway_stamps_the_cost_ceiling_from_requirements() -> None:
    from app.contracts.capability_requirements import CapabilityRequirements
    from app.services.provider_gateway import _apply_cost_ceiling
    from tests.unit.test_provider_gateway import _request

    stamped = _apply_cost_ceiling(
        _request(requirements=CapabilityRequirements(max_estimated_cost_usd=0.25))
    )
    assert stamped.cost_ceiling_usd == 0.25
    untouched = _apply_cost_ceiling(_request())
    assert untouched.cost_ceiling_usd is None


def test_debit_rows_carry_the_resolvable_canonical_reference(
    monkeypatch: MonkeyPatch,
) -> None:
    """Issue #314: new debit evidence binds the collision-proof canonical
    candidate id alongside the v1-shaped idempotent debit_id - the
    idempotency identity is never rewritten, and the canonical reference
    makes the row resolvable under identity v2."""

    _seed_cost_scalars()
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: _Response(_SUCCESS_BODY))

    _run_transport(retry_limit=0, execution_id="exec-canonical-ref")

    rows = [
        row
        for row in get_provider_operations_store().list_attempt_debits()
        if row.debit_id.startswith("adbt2:exec-canonical-ref:")
    ]
    assert len(rows) == 1
    assert rows[0].debit_id == _debit_key("exec-canonical-ref", 0)
    assert rows[0].candidate_id_v2 == derive_candidate_identity_v2(
        provider_id="text.local",
        model_family="gpt-5.4",
        model_revision="gpt-5.4",
        deployment=None,
    )
