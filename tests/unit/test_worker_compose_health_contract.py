"""The worker service must not inherit the API image health probe (#369).

This is the test that would have caught the reported defect. The worker service
defined no `healthcheck`, so Docker applied the Dockerfile's HEALTHCHECK, which
probes http://127.0.0.1:8140/health/live. The worker binds no port, so every
probe failed with ConnectionRefusedError and Docker reported a permanently
unhealthy worker while it was executing jobs correctly.

Nothing in the suite could see it, because the defect was an ABSENCE in
docker-compose.yml - and an absent key is invisible to every test that reads
present ones.

Deliberately parsed with a small indentation reader rather than PyYAML. PyYAML
is not a dependency of this service, and `importorskip` would make this file
skip silently in exactly the environments that matter - a health test that
cannot run is the same defect class as a health probe that cannot pass. The
reader is asserted against known content below so it cannot quietly stop finding
the block it is supposed to read.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"
WORKER_SERVICE = "lotus-ai-worker"
API_SERVICE = "lotus-ai"


def _service_block(service_name: str) -> list[str]:
    """Return the lines of one compose service, by indentation.

    Services are two-space indented under `services:`; the block runs until the
    next line at that same indentation or shallower.
    """

    lines = COMPOSE_PATH.read_text(encoding="utf-8").splitlines()
    header = f"  {service_name}:"
    try:
        start = lines.index(header)
    except ValueError as exc:  # pragma: no cover - guarded by the reader test
        raise AssertionError(f"compose service {service_name!r} not found") from exc

    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        block.append(line)
    return block


def _healthcheck_lines(service_name: str) -> list[str]:
    """Lines of a service's healthcheck mapping, or [] when it defines none."""

    block = _service_block(service_name)
    try:
        start = next(i for i, line in enumerate(block) if line.strip() == "healthcheck:")
    except StopIteration:
        return []
    indent = len(block[start]) - len(block[start].lstrip())
    collected: list[str] = []
    for line in block[start + 1 :]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        if line.strip() and not line.strip().startswith("#"):
            collected.append(line.strip())
    return collected


def test_the_block_reader_actually_finds_service_content() -> None:
    """Pin the reader itself.

    Every assertion below is vacuously true if the reader silently returns
    nothing, so this establishes it reads real content first. This is the
    failure mode that makes a config test look like coverage while asserting
    against an empty list.
    """

    worker_block = _service_block(WORKER_SERVICE)

    assert worker_block, "reader returned no lines for the worker service"
    assert any("start-worker.sh" in line for line in worker_block), worker_block[:5]
    assert any("LOTUS_AI_ASYNC_WORKER_ID" in line for line in worker_block)
    # And it must stop at the service boundary rather than swallowing the file.
    assert not any(
        line.strip() == "volumes:" and not line.startswith("    ") for line in worker_block
    )


def test_the_worker_defines_its_own_healthcheck_rather_than_inheriting_one() -> None:
    """The absence that caused the defect. An inherited probe is not a contract."""

    healthcheck = _healthcheck_lines(WORKER_SERVICE)

    assert healthcheck, (
        "The worker service defines no healthcheck, so it inherits the image "
        "HEALTHCHECK, which probes an HTTP port the worker never binds."
    )
    assert any(line.startswith("test:") for line in healthcheck), healthcheck


def test_the_worker_health_probe_is_not_an_http_request_to_the_api_port() -> None:
    """Pins the reported symptom, not merely that a healthcheck exists.

    A worker healthcheck that still called the API probe would satisfy the test
    above while reproducing the defect exactly, so these are separate.
    """

    test_line = next(
        line for line in _healthcheck_lines(WORKER_SERVICE) if line.startswith("test:")
    )

    assert "8140" not in test_line, test_line
    assert "http://" not in test_line, test_line
    assert "urllib" not in test_line, test_line
    assert "app.worker_health_main" in test_line, test_line


def test_the_api_image_probe_that_the_worker_must_not_use_still_exists() -> None:
    """Pin the premise rather than assuming it.

    If the Dockerfile HEALTHCHECK were removed or changed, the assertions about
    8140 and http:// would still pass while guarding nothing - a pin that
    survives the disappearance of the thing it guards against is not a pin.
    """

    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in dockerfile
    assert "8140/health/live" in dockerfile, (
        "The API image probe changed. Re-derive what the worker must not "
        "inherit before relaxing this test."
    )


def test_the_worker_health_bound_detects_a_severed_dependency_in_useful_time() -> None:
    """The issue requires unhealthy 'within the documented bound'.

    interval x retries is what an operator actually waits, so it is asserted
    rather than described - a later edit widening the interval has to confront
    the claim.
    """

    healthcheck = _healthcheck_lines(WORKER_SERVICE)
    interval = next(line for line in healthcheck if line.startswith("interval:"))
    retries = next(line for line in healthcheck if line.startswith("retries:"))

    interval_seconds = int(interval.split(":", 1)[1].strip().removesuffix("s"))
    retry_count = int(retries.split(":", 1)[1].strip())

    assert interval_seconds * retry_count <= 120, healthcheck
    assert retry_count >= 2, "A single failed probe should not flap the container unhealthy."


def test_worker_and_api_health_semantics_stay_distinct() -> None:
    """The API keeps its HTTP probe; the worker must not borrow it."""

    api_healthcheck = _healthcheck_lines(API_SERVICE)
    worker_healthcheck = _healthcheck_lines(WORKER_SERVICE)

    if api_healthcheck:
        api_test = next((line for line in api_healthcheck if line.startswith("test:")), None)
        worker_test = next(line for line in worker_healthcheck if line.startswith("test:"))
        assert api_test != worker_test
