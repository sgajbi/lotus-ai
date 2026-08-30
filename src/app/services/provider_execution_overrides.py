"""Execution-scoped provider overrides (issue #148).

The evaluation runtime executes governed cases against the production task
pipeline. Provider behaviour for a case - a fake transport response, a
simulated provider failure, a probe posture - is injected here through
contextvars, so an override is visible only to the execution that installed
it: concurrent requests in the same process never observe another
execution's override. This replaces module-global patching, which
reconfigured the entire process for the lifetime of a case.

Hermetic execution: the evaluation runtime wraps every case in
``hermetic_provider_execution()``. Under that context the live network
seams refuse to perform real I/O unless an explicit override is installed,
so an evaluation case can never reach a real provider endpoint, whatever
its configuration.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Type-only: the probe module imports the hermetic guard from here at
    # runtime, so a runtime import back into the probe would be circular.
    from app.services.local_openai_compatible_endpoint_probe import (
        LocalOpenAICompatibleEndpointStatus,
    )

TransportPostOverride = Callable[..., dict[str, Any]]

_text_transport_post_override: ContextVar[TransportPostOverride | None] = ContextVar(
    "lotus_ai_text_transport_post_override", default=None
)
_local_probe_status_override: ContextVar[LocalOpenAICompatibleEndpointStatus | None] = ContextVar(
    "lotus_ai_local_probe_status_override", default=None
)
_hermetic_provider_execution: ContextVar[bool] = ContextVar(
    "lotus_ai_hermetic_provider_execution", default=False
)


@contextmanager
def override_text_transport_post(replacement: TransportPostOverride) -> Iterator[None]:
    token = _text_transport_post_override.set(replacement)
    try:
        yield
    finally:
        _text_transport_post_override.reset(token)


def get_text_transport_post_override() -> TransportPostOverride | None:
    return _text_transport_post_override.get()


@contextmanager
def override_local_probe_status(status: LocalOpenAICompatibleEndpointStatus) -> Iterator[None]:
    token = _local_probe_status_override.set(status)
    try:
        yield
    finally:
        _local_probe_status_override.reset(token)


def get_local_probe_status_override() -> LocalOpenAICompatibleEndpointStatus | None:
    return _local_probe_status_override.get()


@contextmanager
def hermetic_provider_execution() -> Iterator[None]:
    token = _hermetic_provider_execution.set(True)
    try:
        yield
    finally:
        _hermetic_provider_execution.reset(token)


def is_hermetic_provider_execution() -> bool:
    return _hermetic_provider_execution.get()


def ensure_network_execution_permitted(*, seam: str) -> None:
    """Fail closed when a hermetic execution reaches a live network seam.

    Raising (rather than returning a synthetic failure) is deliberate: a
    hermetic case that reaches a network seam without an injected response
    is a defect in the case or the runtime, not a provider condition, and
    must surface as an error rather than as fabricated provider telemetry.
    """

    if _hermetic_provider_execution.get():
        raise RuntimeError(
            f"Hermetic evaluation execution reached the live network seam '{seam}' "
            "without an injected response; evaluation cases must never perform "
            "real provider I/O."
        )
