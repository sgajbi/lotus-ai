"""Deterministic validation of every AI output (issue #156, S1+S2).

One validator on the execution path, after the provider call and before
safety redaction (redaction must never be able to erase a fabricated
reference and flip a verdict). Rules:

- ``evidence_grounding``: every ``source_ref``/``source_refs``/
  ``evidence_ref``/``evidence_refs`` value anywhere in the structured
  output must be one of the supplied request ``source_refs`` - a set
  check, not a prompt instruction. Rejects in every profile.
- ``strict_json`` (recorded by the transport): a promoted-profile output
  recovered by balanced-brace salvage is not a validated output.
- ``output_schema``: the structured output must conform to the task's or
  pack family's JSON Schema contract (``contracts/ai-task-outputs/``).
  Promoted rejects violations; local accepts with a warning and marks the
  output UNVALIDATED_LOCAL_ONLY.
- ``contract_missing``: registration refuses contract-less tasks and
  packs, so a missing contract at execution time is a wiring defect -
  promoted fails closed, local marks the output honestly.

Numeric grounding activates in S3 under the same ruleset seam. A
validator fault fails closed as ``VALIDATION_UNAVAILABLE`` - never an
unmarked output.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.contracts.output_validation import (
    OutputValidationOutcome,
    OutputValidationState,
)
from app.services.output_contracts import schema_violations

logger = logging.getLogger(__name__)

RULE_EVIDENCE_GROUNDING = "evidence_grounding"
RULE_STRICT_JSON = "strict_json"
RULE_OUTPUT_SCHEMA = "output_schema"
RULE_NUMERIC_GROUNDING = "numeric_grounding"
RULE_CONTRACT_MISSING = "contract_missing"

_REFERENCE_KEYS = frozenset({"source_ref", "source_refs", "evidence_ref", "evidence_refs"})
_MAX_RECORDED_FINDINGS = 10
_MAX_TRAVERSAL_DEPTH = 24

# The advisor-brief token vocabulary, generalised (issue #156, S3): only
# tokens that carry a percent or currency marker are policed - bare numbers
# in narrative text are deliberately out of scope (counts, ordinals, and
# dates would drown the signal).
_PERCENT_TOKEN_PATTERN = re.compile(r"(?<![\w-])[-+]?\d+(?:\.\d+)?%")
_CURRENCY_TOKEN_PATTERN = re.compile(r"(?<![\w-])[-+]?\$\d[\d,]*(?:\.\d+)?")
_PERCENT_TOLERANCE = 0.02
_CURRENCY_TOLERANCE = 1.0


def validate_provider_output(
    *,
    structured_output: Any,
    supplied_source_refs: list[str],
    salvaged_json: bool,
    runtime_profile: str,
    contract_key: str,
    context_payload: dict[str, Any] | None = None,
) -> OutputValidationOutcome:
    try:
        return _validate(
            structured_output=structured_output,
            supplied_source_refs=supplied_source_refs,
            salvaged_json=salvaged_json,
            runtime_profile=runtime_profile,
            contract_key=contract_key,
            context_payload=context_payload or {},
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
    contract_key: str,
    context_payload: dict[str, Any],
) -> OutputValidationOutcome:
    failed_rule_ids: list[str] = []
    findings: list[str] = []
    local_only = False

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

    ungrounded_tokens = _ungrounded_numeric_tokens(
        structured_output, basis=_numeric_basis(context_payload)
    )
    if ungrounded_tokens:
        failed_rule_ids.append(RULE_NUMERIC_GROUNDING)
        for token in ungrounded_tokens[:_MAX_RECORDED_FINDINGS]:
            findings.append(
                f"{RULE_NUMERIC_GROUNDING}: narrative token '{token}' does not trace to "
                "any numeric value supplied in the execution context"
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

    if salvaged_json and runtime_profile != "promoted":
        local_only = True

    violations = schema_violations(contract_key, structured_output)
    if violations is None:
        # Registration refuses a task or pack without a contract, so a
        # missing contract at execution time is a wiring defect: promoted
        # fails closed, local marks the output honestly.
        message = f"{RULE_CONTRACT_MISSING}: no output contract exists for '{contract_key}'"
        if runtime_profile == "promoted":
            failed_rule_ids.append(RULE_CONTRACT_MISSING)
            findings.append(message)
        else:
            local_only = True
            findings.append(f"{message}; accepted unvalidated in the local profile only")
    elif violations:
        if runtime_profile == "promoted":
            failed_rule_ids.append(RULE_OUTPUT_SCHEMA)
            findings.extend(f"{RULE_OUTPUT_SCHEMA}: {violation}" for violation in violations)
        else:
            local_only = True
            findings.extend(
                f"{RULE_OUTPUT_SCHEMA}: {violation}; accepted with a warning in the "
                "local profile only"
                for violation in violations
            )

    if failed_rule_ids:
        return OutputValidationOutcome(
            validation_state=OutputValidationState.REJECTED,
            failed_rule_ids=failed_rule_ids,
            findings=findings,
        )
    if local_only:
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


def _numeric_basis(context_payload: dict[str, Any]) -> list[float]:
    """Every numeric value supplied anywhere in the execution context."""

    basis: list[float] = []

    def walk(node: Any, depth: int) -> None:
        if depth > _MAX_TRAVERSAL_DEPTH:
            raise ValueError("context payload exceeds the validation traversal depth")
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            basis.append(float(node))  # monetary-float-ok: leak-detection comparison basis
            return
        if isinstance(node, str):
            try:
                basis.append(  # monetary-float-ok: leak-detection comparison basis
                    float(node.replace(",", ""))
                )
            except ValueError:
                pass
            return
        if isinstance(node, dict):
            for child in node.values():
                walk(child, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(context_payload, 0)
    return basis


def _ungrounded_numeric_tokens(value: Any, *, basis: list[float]) -> list[str]:
    """Percent/currency tokens in output narrative that trace to no supplied value."""

    ungrounded: list[str] = []
    seen: set[str] = set()

    def check_text(text: str) -> None:
        for token in _PERCENT_TOKEN_PATTERN.findall(text):
            candidate = float(  # monetary-float-ok: leak-detection comparison of display token
                token.replace("%", "").replace(",", "")
            )
            if (
                not any(abs(candidate - expected) <= _PERCENT_TOLERANCE for expected in basis)
                and token not in seen
            ):
                seen.add(token)
                ungrounded.append(token)
        for token in _CURRENCY_TOKEN_PATTERN.findall(text):
            normalized = token.replace("$", "").replace(",", "")
            if not normalized:
                continue
            candidate = float(  # monetary-float-ok: leak-detection comparison of display token
                normalized
            )
            if (
                not any(abs(candidate - expected) <= _CURRENCY_TOLERANCE for expected in basis)
                and token not in seen
            ):
                seen.add(token)
                ungrounded.append(token)

    def walk(node: Any, depth: int) -> None:
        if depth > _MAX_TRAVERSAL_DEPTH:
            raise ValueError("structured output exceeds the validation traversal depth")
        if isinstance(node, str):
            check_text(node)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(value, 0)
    return ungrounded
