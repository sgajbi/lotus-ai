"""Attempt-level billing truth (issue #232).

Recorded spend must cover every billed attempt of a non-idempotent
generation, not just the served one: a retried 5xx or timeout may have
generated and billed provider-side. The settlement prices actual usage
evidence first, conservative estimates second (identical request body's
input tokens plus the max_output_tokens ceiling), and never bills failures
that cannot have generated (429, connection-level).
"""

from email.message import Message
from io import BytesIO
from urllib import error

from pytest import MonkeyPatch

from app.config import settings
from app.services.provider_budget_policy import record_provider_spend
from app.services.provider_operations_store import get_provider_operations_store
from app.services.provider_usage_accounting import (
    AttemptBillingSettlement,
    UsageCostEstimate,
    settle_attempt_billing,
)


def _seed_cost_scalars() -> None:
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03


_FINAL_COST = UsageCostEstimate(estimated_cost_usd=0.0035, rate_card_ref="default-live-text")


def _settle(
    attempts: list[dict[str, object]], *, posture: str = "conservative"
) -> AttemptBillingSettlement:
    return settle_attempt_billing(
        failed_attempts=attempts,
        posture=posture,
        final_cost=_FINAL_COST,
        final_input_tokens=200,
        max_output_tokens=512,
        model_revision="gpt-5.4",
    )


def test_settlement_prices_each_evidence_class_honestly() -> None:
    _seed_cost_scalars()

    # No failed attempts: the served attempt is the whole bill.
    single = _settle([])
    assert single.estimated_cost_usd == 0.0035
    assert single.failed_attempt_cost_usd is None
    assert single.failed_attempt_cost_basis is None
    assert single.billed_attempt_count == 1

    # Unknown-usage billable-risk failure under the conservative posture:
    # input tokens are the identical request body's 200; output is the
    # 512-token ceiling -> 0.002 + 0.01536.
    conservative = _settle([{"billable_risk": True, "input_tokens": None, "output_tokens": None}])
    assert conservative.failed_attempt_cost_usd == 0.01736
    assert conservative.estimated_cost_usd == 0.02086
    assert conservative.failed_attempt_cost_basis == "CONSERVATIVE_ESTIMATE"
    assert conservative.billed_attempt_count == 2

    # Provider-reported usage on the failed attempt is actual evidence and
    # beats any estimate.
    actual = _settle([{"billable_risk": True, "input_tokens": 200, "output_tokens": 100}])
    assert actual.failed_attempt_cost_usd == 0.005
    assert actual.failed_attempt_cost_basis == "ACTUAL_USAGE"

    mixed = _settle(
        [
            {"billable_risk": True, "input_tokens": 200, "output_tokens": 100},
            {"billable_risk": True, "input_tokens": None, "output_tokens": None},
        ]
    )
    assert mixed.failed_attempt_cost_basis == "MIXED"
    assert mixed.billed_attempt_count == 3
    assert mixed.failed_attempt_cost_usd == 0.02236

    # A failure that cannot have generated (429 refused pre-generation,
    # connection-level) is never billed, whatever the posture.
    unbillable = _settle([{"billable_risk": False, "input_tokens": None, "output_tokens": None}])
    assert unbillable.estimated_cost_usd == 0.0035
    assert unbillable.failed_attempt_cost_basis == "NONE"
    assert unbillable.billed_attempt_count == 1

    # actual_only never estimates - it bills only usage evidence.
    actual_only = _settle(
        [{"billable_risk": True, "input_tokens": None, "output_tokens": None}],
        posture="actual_only",
    )
    assert actual_only.estimated_cost_usd == 0.0035
    assert actual_only.failed_attempt_cost_basis == "NONE"


def test_transport_bills_the_failed_attempt_behind_a_served_retry(
    monkeypatch: MonkeyPatch,
) -> None:
    """The issue's acceptance: fails once with a 5xx, succeeds on retry -
    recorded spend covers both attempts under the conservative posture."""

    from app.providers.local_openai_compatible_text_provider import (
        LocalOpenAICompatibleTextProvider,
    )
    from app.providers.openai_compatible_text_transport import (
        execute_openai_compatible_text_request,
    )
    from tests.unit.test_provider_gateway import _request

    _seed_cost_scalars()
    monkeypatch.setattr("app.services.provider_retry_backoff._sleep", lambda delay: None)
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)

    attempts = {"count": 0}

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'{"id": "resp_billing", "model": "gpt-5.4", "output_text": "OK",'
                b' "usage": {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250}}'
            )

    def _urlopen(request: object, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise error.HTTPError(
                url="http://localhost/v1/responses",
                code=503,
                msg="unavailable",
                hdrs=Message(),
                fp=BytesIO(b"{}"),
            )
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = execute_openai_compatible_text_request(
        descriptor=LocalOpenAICompatibleTextProvider().descriptor,
        request=_request(retry_limit=1),
        api_base="http://localhost:1234/v1",
        api_key=None,
        require_api_key=False,
        model_id="gpt-5.4",
        model_version=None,
    )

    assert attempts["count"] == 2
    assert response.retry_count == 1
    # Final attempt 0.0035 plus the conservative estimate for the failed one
    # (200 input tokens of the identical body + the 512-token ceiling).
    assert response.failed_attempt_cost_usd == 0.01736
    assert response.estimated_cost_usd == 0.02086
    assert response.failed_attempt_cost_basis == "CONSERVATIVE_ESTIMATE"
    assert response.billed_attempt_count == 2
    # The structured echo carries the same summed figure - one cost truth.
    # (The composition detail lives only on the response/audit level: the
    # echo's shape is pinned by the captured pack output contracts.)
    assert response.structured_output["estimated_cost_usd"] == 0.02086
    assert "billed_attempt_count" not in response.structured_output

    # The budget envelope records the summed figure.
    record_provider_spend(response)
    budget = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == 0.02086


def test_a_rate_limited_retry_is_not_billed(monkeypatch: MonkeyPatch) -> None:
    """429 refuses before generation: retried rate-limits carry no billable
    risk and the settlement says NONE."""

    from app.providers.local_openai_compatible_text_provider import (
        LocalOpenAICompatibleTextProvider,
    )
    from app.providers.openai_compatible_text_transport import (
        execute_openai_compatible_text_request,
    )
    from tests.unit.test_provider_gateway import _request

    _seed_cost_scalars()
    monkeypatch.setattr("app.services.provider_retry_backoff._sleep", lambda delay: None)
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)

    attempts = {"count": 0}

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'{"id": "resp_429", "model": "gpt-5.4", "output_text": "OK",'
                b' "usage": {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250}}'
            )

    def _urlopen(request: object, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise error.HTTPError(
                url="http://localhost/v1/responses",
                code=429,
                msg="rate limited",
                hdrs=Message(),
                fp=BytesIO(b"{}"),
            )
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = execute_openai_compatible_text_request(
        descriptor=LocalOpenAICompatibleTextProvider().descriptor,
        request=_request(retry_limit=1),
        api_base="http://localhost:1234/v1",
        api_key=None,
        require_api_key=False,
        model_id="gpt-5.4",
        model_version=None,
    )

    assert response.retry_count == 1
    assert response.estimated_cost_usd == 0.0035
    assert response.failed_attempt_cost_usd is None
    assert response.failed_attempt_cost_basis == "NONE"
    assert response.billed_attempt_count == 1
