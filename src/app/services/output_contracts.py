"""Per-task output contracts as data (issue #156, S2).

One JSON Schema per registered task id and per workflow-pack family, under
``contracts/ai-task-outputs/``. The schema is the validation authority for
the structured output; ``output_contract_notes`` remains prompt guidance
only. Resolution is by execution context, never by sniffing the output: a
pack-bound execution validates against its pack family's contract, any
other execution against its task id's contract.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts" / "ai-task-outputs"
_CONTRACT_VERSION = "v1"


def output_contract_path(contract_key: str) -> Path:
    return _CONTRACTS_DIR / f"{contract_key}.{_CONTRACT_VERSION}.json"


def output_contract_exists(contract_key: str) -> bool:
    return output_contract_path(contract_key).is_file()


def list_output_contract_keys() -> list[str]:
    if not _CONTRACTS_DIR.is_dir():
        return []
    suffix = f".{_CONTRACT_VERSION}.json"
    return sorted(
        entry.name.removesuffix(suffix)
        for entry in _CONTRACTS_DIR.iterdir()
        if entry.name.endswith(suffix)
    )


@lru_cache(maxsize=64)
def _load_validator(contract_key: str) -> Draft202012Validator | None:
    path = output_contract_path(contract_key)
    if not path.is_file():
        return None
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def reset_output_contract_cache() -> None:
    _load_validator.cache_clear()


def schema_violations(contract_key: str, structured_output: Any) -> list[str] | None:
    """Bounded violation statements, or None when no contract exists.

    An empty list means the output conforms. Messages are bounded and name
    the JSON path so an operator can locate the offending field without the
    output itself being echoed.
    """

    validator = _load_validator(contract_key)
    if validator is None:
        return None
    violations: list[str] = []
    for error in sorted(validator.iter_errors(structured_output), key=lambda e: str(e.json_path)):
        violations.append(f"{error.json_path}: {error.message[:200]}")
        if len(violations) >= 10:
            violations.append("further schema violations withheld from this summary")
            break
    return violations
