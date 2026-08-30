"""Provider metrics and the metric-vocabulary guard (issue #152, slice 2)."""

from __future__ import annotations

import re
from pathlib import Path

from prometheus_client import REGISTRY

from app.services.provider_metrics import (
    METRIC_NAMES,
    record_provider_attempt,
)

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"


def _counter_value(name: str, **labels: str) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


def test_record_provider_attempt_counts_and_observes() -> None:
    before = _counter_value(
        "lotus_ai_provider_requests_total",
        provider_id="text.metrics-test",
        model_id="metrics-model",
        outcome="success",
    )
    record_provider_attempt(
        provider_id="text.metrics-test",
        model_id="metrics-model",
        outcome="success",
        latency_seconds=0.123,
    )
    after = _counter_value(
        "lotus_ai_provider_requests_total",
        provider_id="text.metrics-test",
        model_id="metrics-model",
        outcome="success",
    )
    assert after == before + 1.0

    observed = REGISTRY.get_sample_value(
        "lotus_ai_provider_latency_seconds_count",
        {"provider_id": "text.metrics-test", "model_id": "metrics-model"},
    )
    assert observed is not None and observed >= 1.0


def test_unbounded_outcomes_and_missing_model_are_normalized() -> None:
    before = _counter_value(
        "lotus_ai_provider_requests_total",
        provider_id="text.metrics-test",
        model_id="unknown",
        outcome="failed",
    )
    record_provider_attempt(
        provider_id="text.metrics-test",
        model_id=None,
        outcome="exploded-in-a-new-way",
        latency_seconds=0.001,
    )
    after = _counter_value(
        "lotus_ai_provider_requests_total",
        provider_id="text.metrics-test",
        model_id="unknown",
        outcome="failed",
    )
    assert after == before + 1.0


def test_record_provider_attempt_is_fail_open() -> None:
    # A non-numeric latency would raise inside the client; the recorder must not.
    record_provider_attempt(
        provider_id="text.metrics-test",
        model_id="metrics-model",
        outcome="success",
        latency_seconds="not-a-number",  # type: ignore[arg-type]
    )


def test_every_metric_constructed_in_src_is_in_the_vocabulary() -> None:
    """The vocabulary guard: every prometheus metric name constructed under
    src/ must be declared in METRIC_NAMES and carry the lotus_ai_ prefix, so
    names cannot drift per-module."""

    constructor = re.compile(
        r"\b(?:Counter|Histogram|Gauge|Summary)\(\s*([A-Za-z_][A-Za-z0-9_]*|[\"'][^\"']+[\"'])"
    )
    name_literal = re.compile(r"[\"']([^\"']+)[\"']")
    constructed: set[str] = set()
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "prometheus_client" not in text:
            # collections.Counter and friends are not metrics; only modules
            # importing prometheus_client can construct one.
            continue
        for argument in constructor.findall(text):
            literal = name_literal.fullmatch(argument)
            if literal is not None:
                constructed.add(literal.group(1))
                continue
            # The name is a module constant: resolve it in the same file, and
            # refuse unresolvable constructions - a metric the guard cannot
            # see is a metric outside the vocabulary.
            binding = re.search(rf"^{argument}\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
            assert binding is not None, f"unresolvable metric name in {path.name}: {argument}"
            constructed.add(binding.group(1))

    assert constructed == METRIC_NAMES
    assert all(name.startswith("lotus_ai_") for name in constructed)
