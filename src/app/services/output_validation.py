"""Deterministic validation of every AI output (issue #156, S1).

One validator on the execution path, after the provider call and before
safety redaction (redaction must never be able to erase a fabricated
reference and flip a verdict). S1 ships the rules that need no per-task
contract:

- ``evidence_grounding``: every ``source_ref``/``source_refs``/
  ``evidence_ref``/``evidence_refs`` value anywhere in the structured
  output must be one of the supplied request ``source_refs`` - a set
  check, not a prompt instruction.
- ``strict_json`` (recorded by the transport): a promoted-profile output
  recovered by balanced-brace salvage is not a validated output.

Per-task schema contracts and numeric grounding activate in later slices
under the same ruleset seam. A validator fault fails closed as
``VALIDATION_UNAVAILABLE`` - never an unmarked output.
"""

from __future__ import annotations

import logging
from typing import Any

from app.contracts.output_validation import (
    OutputValidationOutcome,
    OutputValidationState,
)

logger = logging.getLogger(__name__)

RULE_EVIDENCE_GROUNDING = "evidence_grounding"
RULE_STRICT_JSON = "strict_json"

_REFERENCE_KEYS = frozenset({"source_ref", "source_refs", "evidence_ref", "evidence_refs"})
_MAX_RECORDED_FINDINGS = 10
_MAX_TRAVERSAL_DEPTH = 24


def validate_provider_output(
    *,
    structured_output: Any,
    supplied_source_refs: list[str],
    salvaged_json: bool,
    runtime_profile: str,
) -> OutputValidationOutcome:
    try:
        return _validate(
            structured_output=structured_output,
            supplied_source_refs=supplied_source_refs,
            salvaged_json=salvaged_json,
            runtime_profile=runtime_profile,
        )
    except Exception:  # noqa: BLE001 - a validator fault must fail closed, never fall open
        logger.exception("output validation fault; failing closed as VALIDATION_UNAVAILABLE")
        return OutputValidationOutcome(
            validation_state=OutputValidationState.VALIDATION_UNAVAILABLE,
            findings=["The output validator faulted; the output is withheld fail-closed."],
        )


def _validate(
    *,
    structured_output: Any,
    supplied_source_refs: list[str],
    salvaged_json: bool,
    runtime_profile: str,
) -> OutputValidationOutcome:
    failed_rule_ids: list[str] = []
    findings: list[str] = []

    unsupported = _ungrounded_references(
        structured_output, supplied={ref for ref in supplied_source_refs if ref}
    )
    if unsupported:
        failed_rule_ids.append(RULE_EVIDENCE_GROUNDING)
        for reference in unsupported[:_MAX_RECORDED_FINDINGS]:
            findings.append(
                f"{RULE_EVIDENCE_GROUNDING}: output references evidence "
                f"'{reference}' that was not supplied to this execution"
            )
        if len(unsupported) > _MAX_RECORDED_FINDINGS:
            findings.append(
                f"{RULE_EVIDENCE_GROUNDING}: {len(unsupported) - _MAX_RECORDED_FINDINGS} "
                "further unsupported references withheld from this summary"
            )

    if salvaged_json:
        if runtime_profile == "promoted":
            failed_rule_ids.append(RULE_STRICT_JSON)
            findings.append(
                f"{RULE_STRICT_JSON}: the provider answer was not a strict JSON document; "
                "salvaged output is not accepted in the promoted profile"
            )
        else:
            findings.append(
                f"{RULE_STRICT_JSON}: the provider answer required balanced-brace salvage; "
                "accepted unvalidated in the local profile only"
            )

    if failed_rule_ids:
        return OutputValidationOutcome(
            validation_state=OutputValidationState.REJECTED,
            failed_rule_ids=failed_rule_ids,
            findings=findings,
        )
    if salvaged_json:
        return OutputValidationOutcome(
            validation_state=OutputValidationState.UNVALIDATED_LOCAL_ONLY,
            findings=findings,
        )
    return OutputValidationOutcome(
        validation_state=OutputValidationState.VALIDATED,
        findings=findings,
    )


def _ungrounded_references(value: Any, *, supplied: set[str]) -> list[str]:
    """Every reference value in the output that is not in the supplied set.

    The traversal is shape-agnostic: any mapping key named like a reference
    carries either a string or a list of strings; non-string entries under a
    reference key are themselves violations (a fabricated structure is not
    grounded evidence). Order of first appearance, deduplicated.
    """

    unsupported: list[str] = []
    seen: set[str] = set()

    def record(reference: Any, depth: int) -> None:
        if isinstance(reference, str):
            if reference and reference not in supplied and reference not in seen:
                seen.add(reference)
                unsupported.append(reference)
            return
        if isinstance(reference, (dict, list)):
            # The domain vocabulary nests structured evidence entries under
            # reference keys (e.g. advisor-brief ``evidence_refs`` fact
            # objects whose ``source_ref`` is the string reference): recurse,
            # so the inner string references are checked.
            walk(reference, depth + 1)
            return
        marker = f"<non-string reference: {type(reference).__name__}>"
        if marker not in seen:
            seen.add(marker)
            unsupported.append(marker)

    def walk(node: Any, depth: int) -> None:
        if depth > _MAX_TRAVERSAL_DEPTH:
            raise ValueError("structured output exceeds the validation traversal depth")
        if isinstance(node, dict):
            for key, child in node.items():
                if isinstance(key, str) and key in _REFERENCE_KEYS:
                    if isinstance(child, list):
                        for item in child:
                            record(item, depth)
                    else:
                        record(child, depth)
                else:
                    walk(child, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(value, 0)
    return unsupported
